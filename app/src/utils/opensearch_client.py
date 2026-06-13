"""
src/utils/opensearch_client.py
Amazon OpenSearch Service client — k-NN vector search for policy retrieval.
"""
import json
import logging
from typing import List, Dict

import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

logger = logging.getLogger(__name__)

POLICY_MAPPING = {
    "settings": {"index": {"knn": True, "knn.space_type": "cosinesimil", "number_of_shards": 1, "number_of_replicas": 1}},
    "mappings": {"properties": {
        "policy_id":   {"type": "keyword"},
        "source_file": {"type": "keyword"},
        "chunk_text":  {"type": "text", "analyzer": "english"},
        "chunk_index": {"type": "integer"},
        "embedding":   {"type": "knn_vector", "dimension": 1024, "method": {"name": "hnsw", "space_type": "cosinesimil", "engine": "nmslib", "parameters": {"ef_construction": 128, "m": 16}}},
    }},
}


class OpenSearchPolicyStore:
    def __init__(self, endpoint: str, index: str, region: str, bedrock_client, username: str = "", password: str = "") -> None:
        self.endpoint = endpoint
        self.index    = index
        self.region   = region
        self.bedrock  = bedrock_client
        self._client  = self._build_client(endpoint, region, username, password)

    def _build_client(self, endpoint: str, region: str, username: str, password: str) -> OpenSearch:
        host = endpoint.replace("https://", "").replace("http://", "").rstrip("/")
        if username and password:
            return OpenSearch(hosts=[{"host": host, "port": 443}], http_auth=(username, password), use_ssl=True, verify_certs=True, connection_class=RequestsHttpConnection)
        creds  = boto3.Session().get_credentials()
        awsauth = AWS4Auth(creds.access_key, creds.secret_key, region, "es", session_token=creds.token)
        return OpenSearch(hosts=[{"host": host, "port": 443}], http_auth=awsauth, use_ssl=True, verify_certs=True, connection_class=RequestsHttpConnection)

    def create_index(self, delete_existing: bool = False) -> bool:
        if self._client.indices.exists(index=self.index):
            if not delete_existing:
                return False
            self._client.indices.delete(index=self.index)
        self._client.indices.create(index=self.index, body=POLICY_MAPPING)
        return True

    def index_policies(self, chunks: List[Dict]) -> int:
        self.create_index()
        indexed = 0
        for chunk in chunks:
            try:
                doc = {**chunk, "embedding": self.bedrock.embed_text(chunk["chunk_text"])}
                self._client.index(index=self.index, body=doc, id=f"{chunk['policy_id']}-{chunk.get('chunk_index',0)}", refresh=True)
                indexed += 1
            except Exception as exc:
                logger.error("Failed indexing chunk %s: %s", chunk.get("policy_id"), exc)
        return indexed

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        vec  = self.bedrock.embed_text(query)
        body = {"size": top_k, "query": {"knn": {"embedding": {"vector": vec, "k": top_k}}}, "_source": ["policy_id", "source_file", "chunk_text"]}
        try:
            resp = self._client.search(index=self.index, body=body)
            return [{"chunk": h["_source"]["chunk_text"], "source": h["_source"]["source_file"], "policy_id": h["_source"]["policy_id"], "score": round(h["_score"], 4)} for h in resp["hits"]["hits"]]
        except Exception as exc:
            logger.error("OpenSearch search failed: %s", exc)
            return []

    def is_ready(self) -> bool:
        try:
            return self._client.indices.exists(index=self.index) and self._client.count(index=self.index)["count"] > 0
        except Exception:
            return False

    def chunk_count(self) -> int:
        try:
            return self._client.count(index=self.index)["count"]
        except Exception:
            return 0
