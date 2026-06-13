"""
src/utils/bedrock_client.py
Amazon Bedrock client wrapper — Claude LLM + Titan text embeddings.
"""
import json
import logging

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class BedrockClient:
    def __init__(self, region: str, llm_model: str, embed_model: str, max_tokens: int = 2048) -> None:
        self.region      = region
        self.llm_model   = llm_model
        self.embed_model = embed_model
        self.max_tokens  = max_tokens
        self._client     = boto3.client("bedrock-runtime", region_name=region)

    def invoke_llm(self, prompt: str, system: str = "") -> str:
        body: dict = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens":        self.max_tokens,
            "messages":          [{"role": "user", "content": prompt}],
        }
        if system:
            body["system"] = system
        try:
            resp   = self._client.invoke_model(modelId=self.llm_model, body=json.dumps(body), contentType="application/json", accept="application/json")
            result = json.loads(resp["body"].read())
            return result["content"][0]["text"]
        except ClientError as exc:
            logger.error("Bedrock LLM error: %s", exc)
            raise

    def embed_text(self, text: str) -> list[float]:
        body = {"inputText": text[:8000], "dimensions": 1024, "normalize": True}
        try:
            resp   = self._client.invoke_model(modelId=self.embed_model, body=json.dumps(body), contentType="application/json", accept="application/json")
            result = json.loads(resp["body"].read())
            return result["embedding"]
        except ClientError as exc:
            logger.error("Bedrock embed error: %s", exc)
            raise

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_text(t) for t in texts]
