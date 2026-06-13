"""
src/data/seed_opensearch.py
Chunks all 12 policy .txt files, embeds them via Bedrock Titan,
and upserts them into Amazon OpenSearch Service.

Called by:
  POST /admin/seed-policies  — via the API route in routes.py
  The seeding script at app/scripts/seed.py — for manual / CI use

Chunking strategy
─────────────────
  Each policy document is split into overlapping 300-word windows
  with 50-word overlap.  Overlap ensures sentences that span a chunk
  boundary are still retrievable.  This mirrors the strategy used in v1.
"""
import logging
import re
from pathlib import Path

from src.data.generate_policies import generate_policy_files
from src.utils.bedrock_client import BedrockClient
from src.utils.opensearch_client import OpenSearchPolicyStore
from src.config import settings

logger = logging.getLogger(__name__)

CHUNK_SIZE = 300   # words per chunk
CHUNK_OVER = 50    # overlap words


def _split_into_chunks(text: str, policy_id: str) -> list[dict]:
    """Split policy text into overlapping word-window chunks."""
    text   = re.sub(r"\s+", " ", text).strip()
    words  = text.split()
    step   = max(1, CHUNK_SIZE - CHUNK_OVER)
    chunks = []
    for idx, start in enumerate(range(0, len(words), step)):
        chunk_text = " ".join(words[start: start + CHUNK_SIZE])
        if len(chunk_text) > 40:
            chunks.append({
                "policy_id":   policy_id,
                "source_file": policy_id,
                "chunk_text":  chunk_text,
                "chunk_index": idx,
            })
    return chunks


def seed_policies_into_opensearch(policies_dir: Path | None = None) -> dict:
    """
    Main entry point.

    1. Writes policy .txt files to disk if they don't already exist.
    2. Reads each file, splits into chunks.
    3. Embeds each chunk via Bedrock Titan.
    4. Upserts into OpenSearch with k-NN mapping.

    Returns a summary dict.
    """
    # Resolve policies directory
    if policies_dir is None:
        base        = Path(__file__).parent.parent.parent
        policies_dir = base / "data" / "policies"

    policies_dir = Path(policies_dir)

    # Generate .txt files if absent
    txt_files = list(policies_dir.glob("*.txt"))
    if not txt_files:
        logger.info("Policy files not found — generating now")
        generate_policy_files(policies_dir)
        txt_files = list(policies_dir.glob("*.txt"))

    # Build Bedrock client
    bedrock = BedrockClient(
        region      = settings.BEDROCK_REGION,
        llm_model   = settings.BEDROCK_LLM_MODEL,
        embed_model = settings.BEDROCK_EMBED_MODEL,
    )

    # Build OpenSearch client
    store = OpenSearchPolicyStore(
        endpoint       = settings.OPENSEARCH_ENDPOINT,
        index          = settings.OPENSEARCH_INDEX,
        region         = settings.AWS_REGION,
        bedrock_client = bedrock,
        username       = settings.OPENSEARCH_USERNAME,
        password       = settings.OPENSEARCH_PASSWORD,
    )

    # Recreate index (delete if exists, re-create with k-NN mapping)
    store.create_index(delete_existing=True)

    # Chunk and index each policy
    total_chunks  = 0
    total_indexed = 0
    for fpath in sorted(txt_files):
        policy_id = fpath.stem
        text      = fpath.read_text(encoding="utf-8")
        chunks    = _split_into_chunks(text, policy_id)
        indexed   = store.index_policies(chunks)
        total_chunks  += len(chunks)
        total_indexed += indexed
        logger.info("Indexed %s: %d/%d chunks", policy_id, indexed, len(chunks))

    summary = {
        "policy_files": len(txt_files),
        "total_chunks": total_chunks,
        "indexed":      total_indexed,
        "failed":       total_chunks - total_indexed,
        "index":        settings.OPENSEARCH_INDEX,
    }
    logger.info("Seeding complete: %s", summary)
    return summary
