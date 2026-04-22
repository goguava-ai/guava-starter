"""
PostgreSQL pgvector RAG: durable vector storage in your existing Postgres.

Uses PgVectorStore to embed policy documents with Vertex AI and store the
vectors in a PostgreSQL table with the pgvector extension. Unlike LanceDB
(file-based), a Postgres-backed store is shared across multiple processes
and survives full restarts without re-embedding — ideal when you already
run Postgres and want durable, multi-instance RAG.

The pgvector extension adds an HNSW index on the embedding column for fast
approximate nearest-neighbor search via cosine similarity.

Requires:
    pip install 'gridspace-guava[pgvector]'
    # PostgreSQL with pgvector extension (e.g. pgvector/pgvector Docker image)

Environment variables:
    DATABASE_URL  — Postgres connection string
                    e.g. postgresql://user:pass@localhost:5432/mydb

To run a local Postgres with pgvector:
    docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=pass pgvector/pgvector:pg16
"""

import guava
import os
import logging
from guava import logging_utils
from pathlib import Path

from google import genai
from guava.helpers.rag import DocumentQA
from guava.helpers.pgvector import PgVectorStore
from guava.helpers.vertexai import VertexAIEmbedding

logger = logging.getLogger(__name__)

# Load all policy documents and build the vector index at startup.
# PgVectorStore persists embeddings in Postgres, so documents are only
# embedded on first run (DocumentQA skips indexing when the table is populated).
genai_client = genai.Client(vertexai=True)

DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "docs"
DOCUMENTS = [p.read_text() for p in sorted(DOCS_DIR.glob("*.txt"))]

DOCUMENT_QA = DocumentQA(
    documents=DOCUMENTS,
    store=PgVectorStore(
        db_url=os.environ["DATABASE_URL"],
        embedding_model=VertexAIEmbedding(client=genai_client),
    ),
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
