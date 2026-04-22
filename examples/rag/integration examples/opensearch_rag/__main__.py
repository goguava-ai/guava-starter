"""
Amazon OpenSearch RAG: managed neural hybrid search with Gemini answers.

Uses OpenSearch's native Neural Search capabilities. By defining a
"semantic" field in the index, OpenSearch automatically generates vector
embeddings during both indexing and querying using a model hosted within
the service — no local embedding needed. A Search Pipeline handles score
normalization and combination natively.

The OpenSearchVectorStore class implements the guava VectorStore ABC.
Because OpenSearch handles embedding server-side, add_texts just sends
raw text — no Vertex AI call is needed for indexing. Gemini via Vertex AI
is used only for the final answer generation step.

Requires:
    pip install opensearch-py requests-aws4auth boto3

Environment variables:
    OPENSEARCH_ENDPOINT  — your OpenSearch domain endpoint
    OPENSEARCH_MODEL_ID  — ID of the embedding model deployed in OpenSearch
    AWS_DEFAULT_REGION   — AWS region (default: us-east-1)
"""

import logging
import os
from pathlib import Path

import boto3
import guava
from google import genai
from guava import logging_utils
from guava.helpers.rag import DocumentQA, VectorStore, chunk_document
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

logger = logging.getLogger(__name__)

DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "docs"
DOCUMENTS = [p.read_text() for p in sorted(DOCS_DIR.glob("*.txt"))]

INDEX_NAME = "policy-documents"
PIPELINE_NAME = "hybrid-rrf-pipeline"
MODEL_ID = os.environ["OPENSEARCH_MODEL_ID"]


class OpenSearchVectorStore(VectorStore):
    """VectorStore backed by Amazon OpenSearch neural hybrid search.

    OpenSearch handles embedding internally using a deployed ML model —
    add_texts sends raw text and OpenSearch stores + indexes the vectors
    automatically. Search uses a hybrid BM25 + neural kNN query with
    server-side score normalization via a Search Pipeline.
    """

    def __init__(self, client: OpenSearch, index: str, model_id: str, pipeline: str):
        self._client = client
        self._index = index
        self._model_id = model_id
        self._pipeline = pipeline
        self._offset = 0
        self._ensure_pipeline()
        self._ensure_index()
        if self._client.indices.exists(index=self._index):
            self._offset = self._client.count(index=self._index)["count"]

    def _ensure_pipeline(self) -> None:
        self._client.transport.perform_request(
            "PUT",
            f"/_search/pipeline/{self._pipeline}",
            body={
                "description": "Normalize and combine BM25 + kNN scores",
                "phase_results_processors": [{
                    "normalization-processor": {
                        "normalization": {"technique": "min_max"},
                        "combination": {"technique": "arithmetic_mean"},
                    }
                }],
            },
        )

    def _ensure_index(self) -> None:
        if not self._client.indices.exists(index=self._index):
            logger.info("Creating OpenSearch index '%s'...", self._index)
            self._client.indices.create(
                index=self._index,
                body={
                    "settings": {"index": {"knn": True}},
                    "mappings": {
                        "properties": {
                            # OpenSearch auto-vectorizes "semantic" fields using model_id
                            "text": {"type": "semantic", "model_id": self._model_id},
                        }
                    },
                },
            )

    def add_texts(self, texts: list[str]) -> list[str]:
        ids = [str(self._offset + i) for i in range(len(texts))]
        for doc_id, text in zip(ids, texts):
            self._client.index(
                index=self._index,
                id=doc_id,
                body={"text": text},
            )
        self._client.indices.refresh(index=self._index)
        self._offset += len(texts)
        logger.info("Indexed %d chunks into OpenSearch.", len(texts))
        return ids

    def upsert_texts(self, ids: list[str], texts: list[str]) -> None:
        for doc_id, text in zip(ids, texts):
            self._client.index(
                index=self._index,
                id=doc_id,
                body={"text": text},
            )
        self._client.indices.refresh(index=self._index)

    def delete(self, ids: list[str]) -> None:
        for doc_id in ids:
            self._client.delete(index=self._index, id=doc_id, ignore=[404])
        self._client.indices.refresh(index=self._index)

    def search(self, query: str, k: int = 5) -> list[str]:
        response = self._client.search(
            index=self._index,
            params={"search_pipeline": self._pipeline},
            body={
                "size": k,
                "_source": ["text"],
                "query": {
                    "hybrid": {
                        "queries": [
                            {"match": {"text": query}},
                            {"neural": {"text": {"query_text": query, "k": k * 3}}},
                        ]
                    }
                },
            },
        )
        return [hit["_source"]["text"] for hit in response["hits"]["hits"]]

    def clear(self) -> None:
        self._client.delete_by_query(index=self._index, body={"query": {"match_all": {}}})
        self._client.indices.refresh(index=self._index)
        self._offset = 0

    def count(self) -> int:
        if not self._client.indices.exists(index=self._index):
            return 0
        return self._client.count(index=self._index)["count"]


# Build AWS SigV4 auth from the current credentials
region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
credentials = boto3.Session().get_credentials()
aws_auth = AWS4Auth(
    credentials.access_key, credentials.secret_key,
    region, "es", session_token=credentials.token,
)

host = os.environ["OPENSEARCH_ENDPOINT"].replace("https://", "").replace("http://", "").rstrip("/")
os_client = OpenSearch(
    hosts=[{"host": host, "port": 443}],
    http_auth=aws_auth,
    use_ssl=True,
    connection_class=RequestsHttpConnection,
)

genai_client = genai.Client(vertexai=True)
DOCUMENT_QA = DocumentQA(
    documents=DOCUMENTS,
    store=OpenSearchVectorStore(os_client, INDEX_NAME, MODEL_ID, PIPELINE_NAME),
)

agent = guava.Agent()


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.read_script("Hello, how can I help you today?")


@agent.on_question
def on_question(call: guava.Call, question: str) -> str:
    return DOCUMENT_QA.ask(question)


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
