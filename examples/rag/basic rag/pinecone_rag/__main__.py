"""
Cloud Vector DB RAG: Pinecone as a VectorStore with Pinecone Inference embeddings.

Demonstrates using Pinecone as a cloud-hosted vector database. Documents
are chunked and embedded with Pinecone Inference (multilingual-e5-large, 1024-dim),
then upserted to a Pinecone index. Queries are embedded the same way and
sent to Pinecone for nearest-neighbor search.

Unlike LanceDB (local), Pinecone is a managed service accessible from
anywhere without managing infrastructure. This pattern suits production
deployments where multiple agents share the same knowledge base.

Requires: pip install 'gridspace-guava[pinecone]'

Environment variables:
    PINECONE_API_KEY  — your Pinecone API key
"""

import guava
from guava import logging_utils
import os
from pathlib import Path

from guava.helpers.rag import DocumentQA, PineconeVectorStore

DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "docs"
DOCUMENTS = [p.read_text() for p in sorted(DOCS_DIR.glob("*.txt"))]

DOCUMENT_QA = DocumentQA(
    documents=DOCUMENTS,
    store=PineconeVectorStore(
        api_key=os.environ["PINECONE_API_KEY"],
        index_name="policy-documents",
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
