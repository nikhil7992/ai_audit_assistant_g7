"""
src/agents/audit_agent.py
Audit Agent — synthesises all pipeline outputs into a final report.
Persists report JSON to S3.
"""
import json
import logging
import re
from datetime import datetime

import boto3
from botocore.exceptions import ClientError

from src.config import settings
from src.utils.bedrock_client import BedrockClient

logger = logging.getLogger(__name__)


class AuditAgent:
    def __init__(self) -> None:
        self._bedrock = BedrockClient(
            region      = settings.BEDROCK_REGION,
            llm_model   = settings.BEDROCK_LLM_MODEL,
            embed_model = settings.BEDROCK_EMBED_MODEL,
            max_tokens  = settings.BEDROCK_MAX_TOKENS,
        )
        self._s3 = boto3.client("s3", region_name=settings.AWS_REGION)

    def generate_report(self, expenses: list[dict], validations: list[dict], dup_result: dict, batch_id: str = "") -> dict:
        batch_id = batch_id or f"BATCH-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        report   = self._rule_based(expenses, validations, dup_result, batch_id)

        try:
            summary_prompt = f"""You are a senior corporate expense auditor. Write a professional 4-sentence executive summary.

Batch: {batch_id}
Total expenses: {len(expenses)}
Violations: {sum(1 for v in validations if v.get('compliance_status') != 'COMPLIANT')}
Duplicate pairs: {len(dup_result.get('duplicate_pairs', []))}
Compliance score: {report['compliance_score']}/100
Verdict: {report['overall_verdict']}

Return ONLY a JSON object: {{"executive_summary": "<4 sentences>"}}"""
            raw  = self._bedrock.invoke_llm(summary_prompt)
            raw  = re.sub(r"^```(?:json)?\s*", "", raw.strip())
            raw  = re.sub(r"\s*```$", "", raw)
            data = json.loads(raw)
            report["executive_summary"] = data.get("executive_summary", report["executive_summary"])
        except Exception as exc:
            logger.warning("Bedrock summary failed (%s) — using rule-based summary", exc)

        self._persist(report, batch_id)
        return report

    def _rule_based(self, expenses: list[dict], validations: list[dict], dup_result: dict, batch_id: str) -> dict:
        total    = sum(float(e.get("amount", 0)) for e in expenses)
        approved = rejected = pending = 0.0

        for exp, val in zip(expenses, validations):
            amt = float(exp.get("amount", 0))
            if val.get("compliance_status") in ("CRITICAL", "VIOLATION"):
                rejected += amt
            elif val.get("compliance_status") == "PENDING_REVIEW":
                pending  += amt
            else:
                approved += amt

        for pair in dup_result.get("duplicate_pairs", []):
            rejected += pair.get("amount_at_risk", 0.0)
        approved = max(0.0, total - rejected - pending)

        score = 100
        for val in validations:
            s = val.get("compliance_status", "")
            if s == "CRITICAL":      score -= 15
            elif s == "VIOLATION":   score -= 10
            elif s == "PENDING_REVIEW": score -= 3
        score -= len(dup_result.get("duplicate_pairs", [])) * 8
        score  = max(0, min(100, score))

        confs     = [v.get("confidence_score", 0.8) for v in validations]
        agg_conf  = round(sum(confs) / len(confs), 3) if confs else 0.8

        if score >= 80:   verdict = "APPROVED"
        elif score >= 60: verdict = "PARTIALLY_APPROVED"
        elif score >= 40: verdict = "ESCALATED"
        else:             verdict = "REJECTED"

        findings, fid = [], 1
        for exp, val in zip(expenses, validations):
            for v in val.get("violations", []):
                findings.append({"finding_id": f"F-{fid:03d}", "severity": v.get("severity"), "policy_reference": v.get("policy_ref"), "description": v.get("description"), "amount_impact": exp.get("amount"), "affected_expense": exp.get("document_id"), "confidence_score": val.get("confidence_score", 0.8)})
                fid += 1

        dup_findings = [{"type": p.get("type"), "expense_ids": [p.get("expense_id_1"), p.get("expense_id_2")], "amount_at_risk": p.get("amount_at_risk"), "confidence_score": p.get("confidence_score"), "recommendation": p.get("recommendation")} for p in dup_result.get("duplicate_pairs", [])]

        actions, aid = [], 1
        for pair in dup_result.get("duplicate_pairs", []):
            actions.append({"action_id": f"A-DUP-{aid:03d}", "assignee": "Internal Audit", "priority": "HIGH", "action": f"Investigate {pair.get('type')}: {pair.get('expense_id_1')} ↔ {pair.get('expense_id_2')}", "deadline": "5 business days"})
            aid += 1
        for exp, val in zip(expenses, validations):
            for rec in val.get("recommendations", []):
                actions.append({"action_id": f"A-{aid:03d}", "assignee": val.get("requires_approval_from", "MANAGER"), "priority": "HIGH" if val.get("risk_level") in ("HIGH", "CRITICAL") else "MEDIUM", "action": rec, "deadline": "10 business days"})
                aid += 1

        return {
            "audit_report_id":     batch_id,
            "audit_date":          datetime.now().strftime("%Y-%m-%d"),
            "overall_verdict":     verdict,
            "compliance_score":    score,
            "aggregate_confidence":agg_conf,
            "executive_summary":   f"Batch {batch_id}: {len(expenses)} expenses reviewed, ${total:,.2f} claimed. {len(findings)} findings, {len(dup_result.get('duplicate_pairs',[]))} duplicate pairs. Score: {score}/100.",
            "financial_breakdown": {"total_claimed": round(total, 2), "amount_approved": round(approved, 2), "amount_rejected": round(rejected, 2), "amount_pending_review": round(pending, 2)},
            "key_findings":        findings,
            "duplicate_findings":  dup_findings,
            "action_items":        actions,
            "approval_chain":      {"manager_approval_required": any(v.get("requires_approval_from") in ("MANAGER","VP","CFO") for v in validations), "vp_approval_required": any(v.get("requires_approval_from") in ("VP","CFO") for v in validations), "cfo_approval_required": any(v.get("requires_approval_from") == "CFO" for v in validations)},
            "expense_details":     [{"document_id": e.get("document_id"), "vendor": e.get("vendor"), "amount": e.get("amount"), "compliance_status": v.get("compliance_status"), "confidence_score": v.get("confidence_score"), "requires_approval": v.get("requires_approval_from")} for e, v in zip(expenses, validations)],
            "generated_at":        datetime.now().isoformat(),
        }

    def _persist(self, report: dict, batch_id: str) -> None:
        try:
            self._s3.put_object(
                Bucket      = settings.REPORTS_S3_BUCKET,
                Key         = f"reports/{batch_id}.json",
                Body        = json.dumps(report, default=str),
                ContentType = "application/json",
            )
            logger.info("Report saved to s3://%s/reports/%s.json", settings.REPORTS_S3_BUCKET, batch_id)
        except ClientError as exc:
            logger.error("S3 persist failed: %s", exc)
