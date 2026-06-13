"""
src/agents/duplicate_agent.py
Duplicate Detection Agent — SHA-256 exact match + Bedrock Titan embedding similarity.
"""
import hashlib
import logging
import math
import re
from datetime import datetime

from src.config import settings
from src.utils.bedrock_client import BedrockClient

logger = logging.getLogger(__name__)


class DuplicateAgent:
    def __init__(self) -> None:
        self._bedrock = BedrockClient(
            region      = settings.BEDROCK_REGION,
            llm_model   = settings.BEDROCK_LLM_MODEL,
            embed_model = settings.BEDROCK_EMBED_MODEL,
        )

    def detect(self, expenses: list[dict]) -> dict:
        if len(expenses) < 2:
            return {"duplicate_pairs": [], "flagged_ids": [], "summary": {"total_checked": len(expenses), "exact": 0, "near": 0, "suspected": 0}}

        pairs:   list[dict] = []
        flagged: set[str]   = set()

        # Pass 1 — exact SHA-256
        hashes: dict[str, list] = {}
        for exp in expenses:
            h = hashlib.sha256(self._fingerprint(exp).encode()).hexdigest()
            hashes.setdefault(h, []).append(exp)

        for group in hashes.values():
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    a, b = group[i], group[j]
                    pairs.append(self._make_pair(a, b, "EXACT_DUPLICATE", 1.0, "Identical fingerprint."))
                    flagged.update([a.get("document_id", ""), b.get("document_id", "")])

        # Pass 2 — embedding cosine similarity
        already = {(p["expense_id_1"], p["expense_id_2"]) for p in pairs}
        try:
            texts      = [self._expense_text(e) for e in expenses]
            embeddings = self._bedrock.embed_batch(texts)

            for i in range(len(expenses)):
                for j in range(i + 1, len(expenses)):
                    a, b = expenses[i], expenses[j]
                    if (a.get("document_id"), b.get("document_id")) in already:
                        continue
                    vsim  = self._cosine(embeddings[i], embeddings[j])
                    asim  = self._amount_sim(a.get("amount", 0), b.get("amount", 0))
                    dprox = self._date_proximity(a.get("date", ""), b.get("date", ""))

                    if vsim >= 0.92 and asim >= 0.90 and dprox:
                        conf = round((vsim * 0.5 + asim * 0.3 + 0.2), 3)
                        pairs.append(self._make_pair(a, b, "NEAR_DUPLICATE", conf, f"Semantic sim {vsim:.0%}, amount {asim:.0%}."))
                        flagged.update([a.get("document_id", ""), b.get("document_id", "")])
                    elif vsim >= 0.75 and sum([vsim >= 0.75, asim >= 0.80, dprox]) >= 2:
                        pairs.append(self._make_pair(a, b, "SUSPECTED", round(vsim * asim, 3), f"Partial match {vsim:.0%}."))
                        flagged.update([a.get("document_id", ""), b.get("document_id", "")])

        except Exception as exc:
            logger.warning("Embedding detection failed (%s) — exact only", exc)

        pairs.sort(key=lambda p: p["confidence_score"], reverse=True)
        exact     = sum(1 for p in pairs if p["type"] == "EXACT_DUPLICATE")
        near      = sum(1 for p in pairs if p["type"] == "NEAR_DUPLICATE")
        suspected = sum(1 for p in pairs if p["type"] == "SUSPECTED")

        return {
            "duplicate_pairs": pairs,
            "flagged_ids":     list(flagged),
            "summary":         {"total_checked": len(expenses), "exact": exact, "near": near, "suspected": suspected, "total_issues": len(pairs)},
        }

    def _make_pair(self, a: dict, b: dict, dup_type: str, conf: float, reason: str) -> dict:
        return {
            "type":             dup_type,
            "expense_id_1":     a.get("document_id", ""),
            "expense_id_2":     b.get("document_id", ""),
            "vendor_1":         a.get("vendor", ""),
            "vendor_2":         b.get("vendor", ""),
            "amount_1":         a.get("amount", 0),
            "amount_2":         b.get("amount", 0),
            "confidence_score": conf,
            "amount_at_risk":   max(float(a.get("amount", 0)), float(b.get("amount", 0))),
            "reason":           reason,
            "recommendation":   "REJECT immediately." if dup_type == "EXACT_DUPLICATE" else "Hold pending manual review.",
        }

    def _fingerprint(self, e: dict) -> str:
        v = re.sub(r"\s+", " ", (e.get("vendor") or "").lower().replace(" inc", "").replace(" llc", ""))
        return f"{v}|{float(e.get('amount', 0)):.2f}|{str(e.get('date', ''))[:10]}|{(e.get('category') or '').lower()}"

    def _expense_text(self, e: dict) -> str:
        return f"vendor: {e.get('vendor','')} category: {e.get('category','')} amount: {e.get('amount',0):.2f} description: {e.get('description','')}"

    def _cosine(self, a: list, b: list) -> float:
        dot  = sum(x * y for x, y in zip(a, b))
        norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(x * x for x in b))
        return dot / norm if norm > 0 else 0.0

    def _amount_sim(self, a: float, b: float) -> float:
        if a == 0 and b == 0: return 1.0
        if a == 0 or b == 0:  return 0.0
        return max(0.0, 1.0 - abs(a - b) / max(a, b))

    def _date_proximity(self, d1: str, d2: str) -> bool:
        for fmt in ("%Y-%m-%d", "%B %d, %Y", "%m/%d/%Y"):
            try:
                dt1 = datetime.strptime(d1.strip(), fmt)
                dt2 = datetime.strptime(d2.strip(), fmt)
                return abs((dt1 - dt2).days) <= settings.DUPLICATE_DATE_WINDOW_DAYS
            except (ValueError, AttributeError):
                continue
        return False
