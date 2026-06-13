"""
src/config/settings.py
Centralised application configuration sourced from environment variables.
All values with no default are REQUIRED at runtime — see README.md for full list.
"""
import os
from dotenv import load_dotenv

load_dotenv()


# ── AWS core ──────────────────────────────────────────────────────────────────
AWS_REGION: str       = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
AWS_ACCOUNT_ID: str   = os.getenv("AWS_ACCOUNT_ID", "")       # PLACEHOLDER

# ── Amazon Bedrock ────────────────────────────────────────────────────────────
BEDROCK_REGION: str       = os.getenv("BEDROCK_REGION", "us-east-1")
BEDROCK_LLM_MODEL: str    = os.getenv("BEDROCK_LLM_MODEL", "anthropic.claude-sonnet-4-5")
BEDROCK_EMBED_MODEL: str  = os.getenv("BEDROCK_EMBED_MODEL", "amazon.titan-embed-text-v2:0")
BEDROCK_MAX_TOKENS: int   = int(os.getenv("BEDROCK_MAX_TOKENS", "2048"))

# ── AWS Textract ──────────────────────────────────────────────────────────────
TEXTRACT_S3_BUCKET: str   = os.getenv("TEXTRACT_S3_BUCKET", "")   # PLACEHOLDER

# ── Amazon OpenSearch ─────────────────────────────────────────────────────────
OPENSEARCH_ENDPOINT: str  = os.getenv("OPENSEARCH_ENDPOINT", "")  # PLACEHOLDER
OPENSEARCH_INDEX: str     = os.getenv("OPENSEARCH_INDEX", "expense-policies")
OPENSEARCH_USERNAME: str  = os.getenv("OPENSEARCH_USERNAME", "admin")
OPENSEARCH_PASSWORD: str  = os.getenv("OPENSEARCH_PASSWORD", "")  # PLACEHOLDER
OPENSEARCH_TOP_K: int     = int(os.getenv("OPENSEARCH_TOP_K", "5"))

# ── S3 buckets ────────────────────────────────────────────────────────────────
REPORTS_S3_BUCKET: str    = os.getenv("REPORTS_S3_BUCKET", "")    # PLACEHOLDER

# ── Expense policy thresholds (USD) ──────────────────────────────────────────
MAX_HOTEL_NIGHTLY: float  = float(os.getenv("MAX_HOTEL_NIGHTLY", "250.0"))
MAX_DAILY_MEALS: float    = float(os.getenv("MAX_DAILY_MEALS", "75.0"))
MAX_BUSINESS_MEAL: float  = float(os.getenv("MAX_BUSINESS_MEAL", "100.0"))
MAX_SINGLE_EXPENSE: float = float(os.getenv("MAX_SINGLE_EXPENSE", "5000.0"))

APPROVAL_THRESHOLDS: dict = {
    "SELF":    100.0,
    "MANAGER": 1000.0,
    "VP":      5000.0,
    "CFO":     float("inf"),
}

PROHIBITED_KEYWORDS: list = [
    "spa", "salon", "massage", "gambling", "casino",
    "tobacco", "personal grooming", "gym membership",
]

# ── Duplicate detection ───────────────────────────────────────────────────────
DUPLICATE_AMOUNT_TOLERANCE: float = float(os.getenv("DUPLICATE_AMOUNT_TOLERANCE", "0.10"))
DUPLICATE_DATE_WINDOW_DAYS: int   = int(os.getenv("DUPLICATE_DATE_WINDOW_DAYS", "3"))

# ── Application ───────────────────────────────────────────────────────────────
APP_PORT: int    = int(os.getenv("PORT", "8000"))
APP_ENV: str     = os.getenv("APP_ENV", "dev")
LOG_LEVEL: str   = os.getenv("LOG_LEVEL", "INFO")
