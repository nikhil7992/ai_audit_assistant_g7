"""
src/agents/ocr_agent.py
OCR Agent — AWS Textract document extraction.
Replaces pdfplumber/pytesseract with managed Textract for higher accuracy.
"""
import json
import logging
import re
import uuid

import boto3
from botocore.exceptions import ClientError

from src.config import settings

logger = logging.getLogger(__name__)


class OcrAgent:
    """Extracts structured expense data from PDFs and images using AWS Textract."""

    def __init__(self) -> None:
        self._textract = boto3.client("textract", region_name=settings.AWS_REGION)
        self._s3       = boto3.client("s3",       region_name=settings.AWS_REGION)

    # ── Public API ────────────────────────────────────────────────────────────
    def extract_bytes(self, content: bytes, filename: str) -> dict:
        """Extract from raw file bytes. JSON sidecars are parsed directly."""
        doc_id = filename.rsplit(".", 1)[0]

        if filename.lower().endswith(".json"):
            try:
                raw = json.loads(content.decode("utf-8"))
                return self._parse_sidecar(raw, doc_id)
            except Exception as exc:
                logger.error("JSON parse failed for %s: %s", filename, exc)
                return {"error": str(exc), "document_id": doc_id}

        return self._run_textract_bytes(content, filename, doc_id)

    def extract_s3(self, bucket: str, key: str) -> dict:
        """Extract from an existing S3 object."""
        doc_id = key.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        return self._run_textract_s3(bucket, key, doc_id)

    # ── Textract — upload then analyse ───────────────────────────────────────
    def _run_textract_bytes(self, content: bytes, filename: str, doc_id: str) -> dict:
        s3_key = f"uploads/{uuid.uuid4()}/{filename}"
        try:
            self._s3.put_object(
                Bucket      = settings.TEXTRACT_S3_BUCKET,
                Key         = s3_key,
                Body        = content,
                ContentType = "application/pdf",
            )
        except ClientError as exc:
            logger.error("S3 upload failed: %s", exc)
            return {"error": str(exc), "document_id": doc_id}

        return self._run_textract_s3(settings.TEXTRACT_S3_BUCKET, s3_key, doc_id)

    def _run_textract_s3(self, bucket: str, key: str, doc_id: str) -> dict:
        try:
            resp = self._textract.analyze_document(
                Document      = {"S3Object": {"Bucket": bucket, "Name": key}},
                FeatureTypes  = ["TABLES", "FORMS"],
            )
        except ClientError as exc:
            logger.error("Textract failed for s3://%s/%s: %s", bucket, key, exc)
            return {"error": str(exc), "document_id": doc_id}

        return self._parse_textract_response(resp, doc_id)

    # ── Textract response parser ──────────────────────────────────────────────
    def _parse_textract_response(self, resp: dict, doc_id: str) -> dict:
        blocks      = resp.get("Blocks", [])
        lines: list[str]         = []
        confidences: list[float] = []
        word_map: dict[str, str] = {}
        kv_pairs: dict[str, str] = {}
        table_cells: dict[tuple, str] = {}

        for b in blocks:
            if b["BlockType"] == "LINE":
                lines.append(b.get("Text", ""))
                confidences.append(b.get("Confidence", 0.0))
            elif b["BlockType"] == "WORD":
                word_map[b["Id"]] = b.get("Text", "")
            elif b["BlockType"] == "CELL":
                table_cells[(b.get("RowIndex", 0), b.get("ColumnIndex", 0))] = \
                    self._text_from_block(b, word_map)

        raw_text    = "\n".join(lines)
        avg_conf    = round(sum(confidences) / len(confidences) / 100, 3) if confidences else 0.0

        # Form key-value pairs
        key_blocks = {b["Id"]: b for b in blocks
                      if b["BlockType"] == "KEY_VALUE_SET" and "KEY" in b.get("EntityTypes", [])}
        val_blocks = {b["Id"]: b for b in blocks
                      if b["BlockType"] == "KEY_VALUE_SET" and "VALUE" in b.get("EntityTypes", [])}

        for kb in key_blocks.values():
            kt = self._text_from_block(kb, word_map)
            for rel in kb.get("Relationships", []):
                if rel["Type"] == "VALUE":
                    for vid in rel["Ids"]:
                        vt = self._text_from_block(val_blocks.get(vid, {}), word_map)
                        if kt and vt:
                            kv_pairs[kt.strip().lower()] = vt.strip()

        # Line items from table
        line_items: list[dict] = []
        if table_cells:
            max_row = max(r for r, _ in table_cells)
            max_col = max(c for _, c in table_cells)
            headers = [table_cells.get((1, c), f"col{c}") for c in range(1, max_col + 1)]
            for row in range(2, max_row + 1):
                item = {headers[c - 1]: table_cells.get((row, c), "") for c in range(1, max_col + 1)}
                if any(item.values()):
                    line_items.append(item)

        amount   = self._extract_amount(kv_pairs, raw_text)
        vendor   = self._field(kv_pairs, ["vendor", "merchant", "supplier", "from", "company"])
        date     = self._field(kv_pairs, ["date", "invoice date", "expense date", "transaction date"])
        category = self._field(kv_pairs, ["category", "expense type", "type"])
        emp_name = self._field(kv_pairs, ["employee", "employee name", "submitted by", "name"])
        emp_id   = self._field(kv_pairs, ["employee id", "emp id"])
        dept     = self._field(kv_pairs, ["department", "dept"])
        project  = self._field(kv_pairs, ["project", "project code"])
        desc     = self._field(kv_pairs, ["description", "purpose", "memo"])

        if not vendor:
            m = re.search(r"^([A-Z][A-Za-z &]+(?:Inc\.|LLC|Ltd|Corp|Hotels|Airlines)?)", raw_text.strip(), re.M)
            vendor = m.group(1).strip() if m else ""
        if not date:
            m = re.search(r"\d{4}-\d{2}-\d{2}", raw_text)
            date = m.group(0) if m else ""
        if not category:
            category = self._heuristic_category(raw_text)

        return {
            "document_id":         doc_id,
            "document_type":       "invoice" if "invoice" in raw_text.lower() else "receipt",
            "vendor":              vendor,
            "category":            category,
            "amount":              amount,
            "date":                date,
            "employee_name":       emp_name,
            "employee_id":         emp_id,
            "department":          dept,
            "project_code":        project,
            "description":         desc,
            "line_items":          line_items,
            "raw_text":            raw_text[:2000],
            "extraction_method":   "aws_textract",
            "confidence":          avg_conf,
            "textract_confidence": avg_conf,
        }

    # ── Sidecar JSON parser ───────────────────────────────────────────────────
    def _parse_sidecar(self, raw: dict, doc_id: str) -> dict:
        emp = raw.get("employee", {})
        return {
            "document_id":         raw.get("invoice_id", raw.get("form_id", doc_id)),
            "document_type":       "invoice" if "invoice_id" in raw else "reimbursement_form",
            "vendor":              raw.get("vendor", ""),
            "category":            raw.get("category", ""),
            "amount":              float(raw.get("amount", raw.get("total_claimed", 0.0))),
            "date":                raw.get("date", raw.get("submission_date", "")),
            "employee_name":       emp.get("name", raw.get("employee_name", "")),
            "employee_id":         emp.get("emp_id", raw.get("employee_id", "")),
            "department":          emp.get("dept", raw.get("department", "")),
            "project_code":        emp.get("project", raw.get("project_code", "")),
            "description":         raw.get("description", emp.get("purpose", "")),
            "line_items":          raw.get("line_items", raw.get("expenses", [])),
            "raw_text":            "",
            "extraction_method":   "sidecar_json",
            "confidence":          1.0,
            "textract_confidence": 1.0,
        }

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _text_from_block(self, block: dict, word_map: dict) -> str:
        parts = []
        for rel in block.get("Relationships", []):
            if rel["Type"] == "CHILD":
                for cid in rel["Ids"]:
                    if cid in word_map:
                        parts.append(word_map[cid])
        return " ".join(parts)

    def _extract_amount(self, kv: dict, raw: str) -> float:
        for k in ["total", "amount", "amount due", "grand total", "subtotal"]:
            if k in kv:
                try:
                    return float(kv[k].replace(",", "").replace("$", "").strip())
                except ValueError:
                    pass
        amounts = [float(a.replace(",", "")) for a in re.findall(r"\$\s?([\d,]+\.\d{2})", raw)]
        return max(amounts) if amounts else 0.0

    def _field(self, kv: dict, keys: list[str]) -> str:
        for k in keys:
            if kv.get(k):
                return kv[k]
        return ""

    def _heuristic_category(self, text: str) -> str:
        tl = text.lower()
        for cat, kws in {
            "accommodation": ["hotel", "motel", "lodging"],
            "travel":        ["airline", "airfare", "flight"],
            "meals":         ["restaurant", "dinner", "lunch"],
            "transportation":["uber", "lyft", "taxi"],
            "technology":    ["software", "laptop", "hardware"],
            "wellness":      ["spa", "massage", "gym"],
        }.items():
            if any(k in tl for k in kws):
                return cat
        return "other"
