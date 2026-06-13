"""
src/api/routes.py
All FastAPI route handlers.

Data flow summary
─────────────────
  POST /audit/upload
      → OcrAgent.extract_bytes()  (Textract or sidecar JSON)
      → ValidationAgent.validate() per expense
      → DuplicateAgent.detect()   on full batch
      → AuditAgent.generate_report()
      → returns full AuditReport JSON

  POST /audit/sample
      → generate_all_samples()    (no OCR — already structured)
      → ValidationAgent, DuplicateAgent, AuditAgent  (identical pipeline)

  POST /admin/seed-policies
      → generate_policy_files()   writes 12 .txt policy docs
      → seed_policies_into_opensearch()  chunks → Titan embeds → OpenSearch

  GET /audit/scenarios
      → get_scenario_summary()    returns metadata for all 18 synthetic cases
"""
import logging

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from src.agents.ocr_agent import OcrAgent
from src.agents.validation_agent import ValidationAgent
from src.agents.duplicate_agent import DuplicateAgent
from src.agents.audit_agent import AuditAgent
from src.data.generate_synthetic_data import generate_all_samples, get_scenario_summary

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Health ────────────────────────────────────────────────────────────────────
@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "expense-audit", "version": "2.0.0"}


# ── Audit — upload files ──────────────────────────────────────────────────────
@router.post("/audit/upload")
async def audit_upload(files: list[UploadFile] = File(...)) -> dict:
    """
    Accept PDF or JSON sidecar file uploads, run the full audit pipeline.

    JSON sidecars (produced by write_json_sidecars()) are parsed directly
    by OcrAgent with confidence=1.0, bypassing AWS Textract.
    PDFs are uploaded to S3 and processed by Textract.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")

    ocr     = OcrAgent()
    val     = ValidationAgent()
    dup     = DuplicateAgent()
    auditor = AuditAgent()

    expenses: list[dict] = []
    for f in files:
        content = await f.read()
        result  = ocr.extract_bytes(content, f.filename or "upload")
        if result.get("error"):
            logger.warning("OCR failed for %s: %s", f.filename, result["error"])
        else:
            expenses.append(result)

    if not expenses:
        raise HTTPException(status_code=422, detail="No documents could be extracted.")

    validations = [val.validate(e) for e in expenses]
    dup_result  = dup.detect(expenses)
    return auditor.generate_report(expenses, validations, dup_result)


# ── Audit — synthetic sample dataset ─────────────────────────────────────────
@router.post("/audit/sample")
async def audit_sample() -> dict:
    """
    Run the full audit pipeline on the 18 built-in synthetic expense records.

    The synthetic dataset covers every scenario:
      - 6 clean / compliant expenses
      - 5 policy violations (hotel, meal, prohibited, high-value, late)
      - 3 duplicate pairs (1 exact, 2 near)
      - 4 reimbursement form items

    Identical pipeline to /audit/upload — only the extraction step differs
    (generate_all_samples() returns pre-structured dicts; no OCR call needed).
    Expected output: verdict=ESCALATED, score≈20/100.
    """
    val     = ValidationAgent()
    dup     = DuplicateAgent()
    auditor = AuditAgent()

    # generate_all_samples() returns a summary dict; expenses are under "expenses" key
    result      = generate_all_samples()
    expenses    = result["expenses"]
    validations = [val.validate(e) for e in expenses]
    dup_result  = dup.detect(expenses)
    return auditor.generate_report(expenses, validations, dup_result, "SAMPLE")


# ── Audit — scenario metadata ─────────────────────────────────────────────────
@router.get("/audit/scenarios")
async def list_scenarios() -> dict:
    """
    Return metadata about every synthetic test scenario.
    Useful for understanding what /audit/sample exercises.
    """
    scenarios = get_scenario_summary()
    return {
        "total":      len(scenarios),
        "scenarios":  scenarios,
        "categories": {
            "clean":     sum(1 for s in scenarios if s["scenario"] == "clean"),
            "violation": sum(1 for s in scenarios if s["scenario"] == "violation"),
            "duplicate": sum(1 for s in scenarios if s["scenario"] == "duplicate"),
        },
    }


# ── Validate single expense ───────────────────────────────────────────────────
@router.post("/validate")
async def validate_expense(expense: dict) -> dict:
    """Validate a single expense JSON against company policy."""
    return ValidationAgent().validate(expense)


# ── Policy semantic search ────────────────────────────────────────────────────
class PolicyQueryRequest(BaseModel):
    query: str
    top_k: int = 5


@router.post("/policies/query")
async def query_policies(req: PolicyQueryRequest) -> dict:
    """Semantic search over the OpenSearch policy index."""
    from src.utils.opensearch_client import OpenSearchPolicyStore
    from src.utils.bedrock_client import BedrockClient
    from src.config import settings

    bedrock = BedrockClient(
        region    = settings.BEDROCK_REGION,
        llm_model = settings.BEDROCK_LLM_MODEL,
        embed_model = settings.BEDROCK_EMBED_MODEL,
    )
    store = OpenSearchPolicyStore(
        endpoint       = settings.OPENSEARCH_ENDPOINT,
        index          = settings.OPENSEARCH_INDEX,
        region         = settings.AWS_REGION,
        bedrock_client = bedrock,
        username       = settings.OPENSEARCH_USERNAME,
        password       = settings.OPENSEARCH_PASSWORD,
    )
    return {"query": req.query, "results": store.search(req.query, top_k=req.top_k)}


# ── Reports ───────────────────────────────────────────────────────────────────
@router.get("/reports")
async def list_reports() -> dict:
    import boto3
    from src.config import settings

    s3  = boto3.client("s3", region_name=settings.AWS_REGION)
    res = s3.list_objects_v2(Bucket=settings.REPORTS_S3_BUCKET, Prefix="reports/")
    items = [
        {
            "report_id":     obj["Key"].replace("reports/", "").replace(".json", ""),
            "last_modified": obj["LastModified"].isoformat(),
            "size_bytes":    obj["Size"],
        }
        for obj in res.get("Contents", [])
    ]
    return {"reports": items, "total": len(items)}


@router.get("/reports/{report_id}")
async def get_report(report_id: str) -> dict:
    import json
    import boto3
    from src.config import settings

    s3 = boto3.client("s3", region_name=settings.AWS_REGION)
    try:
        obj = s3.get_object(
            Bucket=settings.REPORTS_S3_BUCKET,
            Key=f"reports/{report_id}.json",
        )
        return json.loads(obj["Body"].read())
    except Exception:
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found.")


# ── Admin — generate data files on disk ──────────────────────────────────────
@router.post("/admin/generate-data")
async def generate_data() -> dict:
    """
    Write the complete synthetic dataset to the data/ directory on disk.

    Produces (matching v1 folder layout exactly):
      data/invoices/      14 x .json + .pdf  (PDFs require reportlab)
      data/forms/          4 x .json + .pdf
      data/ocr_output/    18 x _ocr.json stubs

    Call this once after first deployment so the data folder is populated
    and ready for Path B (upload) and Path C (Textract) testing.
    Idempotent — safe to re-run; files are overwritten.
    """
    base = Path("data")
    result = generate_all_samples(
        invoices_dir   = base / "invoices",
        forms_dir      = base / "forms",
        ocr_output_dir = base / "ocr_output",
    )
    return {
        "status":             "ok",
        "invoices_generated": result["invoices_generated"],
        "forms_generated":    result["forms_generated"],
        "pdfs_generated":     result["pdfs_generated"],
        "invoice_ids":        result["invoice_ids"],
        "form_ids":           result["form_ids"],
    }


# ── Admin — seed OpenSearch with policy embeddings ────────────────────────────
@router.post("/admin/seed-policies")
async def seed_policies() -> dict:
    """
    1. Write 12 policy .txt files to data/policies/
    2. Chunk each file (300-word windows, 50-word overlap)
    3. Embed each chunk via Amazon Bedrock Titan Embed Text v2
    4. Upsert into Amazon OpenSearch Service k-NN index

    Call this once after first deployment, and again any time policies change.
    Idempotent — recreates the index cleanly on each call.
    """
    from src.data.seed_opensearch import seed_policies_into_opensearch
    result = seed_policies_into_opensearch()
    return {"status": "ok", **result}
