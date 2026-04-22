"""
Local Vector DB RAG: ChromaDB as a VectorStore, Gemini for answers.

ChromaDB stores embeddings on disk so they persist across restarts —
documents are only chunked and embedded on first run. ChromaDB handles
embedding internally using its built-in model (all-MiniLM-L6-v2), while
Gemini via Vertex AI generates the final answer.

Requires: pip install 'gridspace-guava[chromadb]'

Data is stored in a local ./chroma_data directory next to this file.
"""

import os
from pathlib import Path

import guava
from guava import logging_utils
from guava.helpers.chromadb import ChromaVectorStore
from guava.helpers.rag import DocumentQA

DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "docs"
DOCUMENTS = [p.read_text() for p in sorted(DOCS_DIR.glob("*.txt"))]

DOCUMENT_QA = DocumentQA(
    documents=DOCUMENTS,
    store=ChromaVectorStore(
        path=str(Path(__file__).parent / "chroma_data"),
        collection_name="policy_documents",
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
