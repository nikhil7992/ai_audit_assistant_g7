"""
src/agents/validation_agent.py
Validation Agent — Amazon Bedrock LLM + OpenSearch semantic RAG.
Returns compliance_status, risk_level, confidence_score, violations.
"""
import json
import logging
import re

from src.config import settings
from src.utils.bedrock_client import BedrockClient
from src.utils.opensearch_client import OpenSearchPolicyStore

logger = logging.getLogger(__name__)


class ValidationAgent:
    def __init__(self) -> None:
        self._bedrock = BedrockClient(
            region      = settings.BEDROCK_REGION,
            llm_model   = settings.BEDROCK_LLM_MODEL,
            embed_model = settings.BEDROCK_EMBED_MODEL,
            max_tokens  = settings.BEDROCK_MAX_TOKENS,
        )
        self._store = OpenSearchPolicyStore(
            endpoint       = settings.OPENSEARCH_ENDPOINT,
            index          = settings.OPENSEARCH_INDEX,
            region         = settings.AWS_REGION,
            bedrock_client = self._bedrock,
            username       = settings.OPENSEARCH_USERNAME,
            password       = settings.OPENSEARCH_PASSWORD,
        )

    def validate(self, expense: dict) -> dict:
        query     = self._build_query(expense)
        retrieved = []
        try:
            if self._store.is_ready():
                retrieved = self._store.search(query, top_k=settings.OPENSEARCH_TOP_K)
        except Exception as exc:
            logger.warning("OpenSearch unavailable (%s) — skipping RAG", exc)

        try:
            return self._validate_with_bedrock(expense, retrieved)
        except Exception as exc:
            logger.warning("Bedrock validation failed (%s) — rule-based fallback", exc)
            return self._validate_rule_based(expense, retrieved)

    # ── Bedrock LLM ───────────────────────────────────────────────────────────
    def _validate_with_bedrock(self, expense: dict, retrieved: list) -> dict:
        policy_context = "\n\n".join(
            f"[{r['source']} | score {r['score']:.3f}]\n{r['chunk']}"
            for r in retrieved
        ) or "No specific policy clauses retrieved."

        prompt = f"""You are a corporate expense compliance auditor.

EXPENSE:
{json.dumps(expense, indent=2, default=str)}

RELEVANT POLICY CLAUSES:
{policy_context}

Return ONLY valid JSON:
{{
  "compliance_status": "COMPLIANT"|"VIOLATION"|"CRITICAL"|"PENDING_REVIEW",
  "risk_level": "LOW"|"MEDIUM"|"HIGH"|"CRITICAL",
  "confidence_score": <float 0.0-1.0>,
  "violations": [{{"policy_ref": "<ref>", "description": "<desc>", "severity": "HIGH"}}],
  "recommendations": ["<action>"],
  "requires_approval_from": "SELF"|"MANAGER"|"VP"|"CFO",
  "reasoning": "<2-3 sentences>"
}}"""

        raw  = self._bedrock.invoke_llm(prompt)
        raw  = re.sub(r"^```(?:json)?\s*", "", raw.strip())
        raw  = re.sub(r"\s*```$", "", raw)
        data = json.loads(raw)
        data["document_id"]        = expense.get("document_id", "")
        data["retrieved_policies"] = retrieved
        data["validation_method"]  = "bedrock_llm"
        return data

    # ── Rule-based fallback ───────────────────────────────────────────────────
    def _validate_rule_based(self, expense: dict, retrieved: list) -> dict:
        violations: list[dict] = []
        recs: list[str]        = []
        amount   = float(expense.get("amount", 0))
        combined = " ".join([
            expense.get("category", ""),
            expense.get("vendor", ""),
            expense.get("description", ""),
        ]).lower()

        for kw in settings.PROHIBITED_KEYWORDS:
            if kw in combined:
                violations.append({"policy_ref": "TP-007", "description": f"Prohibited: '{kw}'", "severity": "CRITICAL"})
                recs.append(f"Reject — prohibited keyword '{kw}' per TP-007.")

        if any(h in combined for h in ["hotel", "marriott", "hilton", "hyatt"]):
            limit = 350.0 if any(c in combined for c in ["new york", "nyc", "san francisco"]) else 250.0
            if amount > limit:
                violations.append({"policy_ref": "TP-002", "description": f"Hotel ${amount:.2f} exceeds ${limit:.2f}/night", "severity": "HIGH"})

        if any(m in (expense.get("category") or "").lower() for m in ["meal", "food", "dining"]):
            if amount > settings.MAX_BUSINESS_MEAL:
                violations.append({"policy_ref": "TP-003", "description": f"Meal ${amount:.2f} exceeds ${settings.MAX_BUSINESS_MEAL:.2f}/person", "severity": "HIGH"})

        if amount <= settings.APPROVAL_THRESHOLDS["SELF"]:         approval = "SELF"
        elif amount <= settings.APPROVAL_THRESHOLDS["MANAGER"]:    approval = "MANAGER"
        elif amount <= settings.APPROVAL_THRESHOLDS["VP"]:         approval = "VP"
        else:
            approval = "CFO"
            violations.append({"policy_ref": "TP-008", "description": f"${amount:.2f} requires CFO approval", "severity": "HIGH"})

        if any(v["severity"] == "CRITICAL" for v in violations):   status, risk, conf = "CRITICAL",       "CRITICAL", 0.95
        elif any(v["severity"] == "HIGH"   for v in violations):   status, risk, conf = "VIOLATION",      "HIGH",     0.88
        elif violations:                                             status, risk, conf = "VIOLATION",      "MEDIUM",   0.80
        elif amount > settings.APPROVAL_THRESHOLDS["MANAGER"]:     status, risk, conf = "PENDING_REVIEW", "MEDIUM",   0.75
        else:                                                        status, risk, conf = "COMPLIANT",      "LOW",      0.92

        if not violations:
            recs.append("Expense appears compliant. Standard approval workflow applies.")

        return {
            "document_id":            expense.get("document_id", ""),
            "compliance_status":      status,
            "risk_level":             risk,
            "confidence_score":       conf,
            "violations":             violations,
            "recommendations":        recs,
            "requires_approval_from": approval,
            "reasoning":              f"{'Found violations.' if violations else 'Passes all checks.'} Amount: ${amount:.2f}.",
            "retrieved_policies":     retrieved,
            "validation_method":      "rule_based",
        }

    def _build_query(self, expense: dict) -> str:
        parts = [expense.get("category", ""), expense.get("vendor", ""),
                 f"${expense.get('amount', 0):.2f}", expense.get("description", "")[:200]]
        return " ".join(p for p in parts if p) or "general expense policy"
