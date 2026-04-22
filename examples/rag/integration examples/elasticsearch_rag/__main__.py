"""
Elasticsearch RAG: hybrid BM25 + kNN search.

Demonstrates using Elasticsearch as the retrieval backend. Elasticsearch
supports both BM25 full-text search and dense vector kNN search in a single
index. At query time both methods run in parallel and their scores are
combined using Reciprocal Rank Fusion — Elasticsearch handles this natively
via the `sub_searches` + `rank` API.

The ElasticsearchVectorStore class implements the guava VectorStore ABC.
Documents are embedded and stored alongside their raw text for BM25 indexing.

Requires:
    pip install elasticsearch

Environment variables:
    ELASTICSEARCH_URL  — Elasticsearch endpoint (default: http://localhost:9200)

To run Elasticsearch locally:
    docker run -d -p 9200:9200 -e "discovery.type=single-node" \\
        -e "xpack.security.enabled=false" elasticsearch:8.15.0
"""

import guava
import os
import logging
from guava import logging_utils
from pathlib import Path

from elasticsearch import Elasticsearch
from google import genai
from guava.helpers.rag import DocumentQA, VectorStore

logger = logging.getLogger(__name__)

DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "docs"
DOCUMENTS = [p.read_text() for p in sorted(DOCS_DIR.glob("*.txt"))]

EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIM = 768
INDEX_NAME = "policy-documents"


class ElasticsearchVectorStore(VectorStore):
    """VectorStore backed by Elasticsearch using BM25 + kNN hybrid search.

    Documents are embedded with Vertex AI and stored with their raw text
    so Elasticsearch can run both BM25 and kNN queries. At search time
    both signals are combined using Elasticsearch's native RRF ranking.
    """

    def __init__(self, client: genai.Client, es: Elasticsearch, index: str,
                 embedding_model: str = EMBEDDING_MODEL):
        self._client = client
        self._es = es
        self._index = index
        self._embedding_model = embedding_model
        self._ensure_index()
        self._offset = self._es.count(index=self._index)["count"]

    def _ensure_index(self) -> None:
        if not self._es.indices.exists(index=self._index):
            logger.info("Creating Elasticsearch index '%s'...", self._index)
            self._es.indices.create(
                index=self._index,
                body={
                    "mappings": {
                        "properties": {
                            "text": {"type": "text"},
                            "embedding": {
                                "type": "dense_vector",
                                "dims": EMBEDDING_DIM,
                                "index": True,
                                "similarity": "cosine",
                            },
                        }
                    }
                },
            )

    def _embed(self, texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
        response = self._client.models.embed_content(
            model=self._embedding_model,
            contents=texts,
            config=genai.types.EmbedContentConfig(
                output_dimensionality=EMBEDDING_DIM,
                task_type=task_type,
            ),
        )
        return [e.values for e in (response.embeddings or []) if e.values is not None]

    def add_texts(self, texts: list[str]) -> list[str]:
        ids = [str(self._offset + i) for i in range(len(texts))]
        embeddings = self._embed(texts, "RETRIEVAL_DOCUMENT")
        for doc_id, text, embedding in zip(ids, texts, embeddings):
            self._es.index(
                index=self._index,
                id=doc_id,
                body={"text": text, "embedding": embedding},
            )
        self._es.indices.refresh(index=self._index)
        self._offset += len(texts)
        logger.info("Indexed %d chunks into Elasticsearch.", len(texts))
        return ids

    def upsert_texts(self, ids: list[str], texts: list[str]) -> None:
        embeddings = self._embed(texts, "RETRIEVAL_DOCUMENT")
        for doc_id, text, embedding in zip(ids, texts, embeddings):
            self._es.index(
                index=self._index,
                id=doc_id,
                body={"text": text, "embedding": embedding},
            )
        self._es.indices.refresh(index=self._index)

    def delete(self, ids: list[str]) -> None:
        for doc_id in ids:
            self._es.delete(index=self._index, id=doc_id, ignore=[404])
        self._es.indices.refresh(index=self._index)

    def search(self, query: str, k: int = 5) -> list[str]:
        query_embedding = self._embed([query], "QUESTION_ANSWERING")[0]
        response = self._es.search(
            index=self._index,
            body={
                "size": k,
                "sub_searches": [
                    {"query": {"match": {"text": query}}},
                    {"knn": {"field": "embedding", "query_vector": query_embedding,
                              "num_candidates": k * 3}},
                ],
                "rank": {"rrf": {"window_size": k * 3}},
            },
        )
        return [hit["_source"]["text"] for hit in response["hits"]["hits"]]

    def clear(self) -> None:
        self._es.delete_by_query(index=self._index, body={"query": {"match_all": {}}})
        self._es.indices.refresh(index=self._index)
        self._offset = 0

    def count(self) -> int:
        if not self._es.indices.exists(index=self._index):
            return 0
        return self._es.count(index=self._index)["count"]


es = Elasticsearch(os.environ.get("ELASTICSEARCH_URL", "http://localhost:9200"))

genai_client = genai.Client(vertexai=True)
DOCUMENT_QA = DocumentQA(
    documents=DOCUMENTS,
    store=ElasticsearchVectorStore(genai_client, es, INDEX_NAME),
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
