"""
Local Vector DB RAG: ChromaDB as a VectorStore, Gemini for answers.

ChromaDB stores embeddings on disk so they persist across restarts —
documents are only chunked and embedded on first run. ChromaDB handles
embedding internally using its built-in model (all-MiniLM-L6-v2), while
Gemini via Vertex AI generates the final answer.

Requires: pip install 'gridspace-guava[chromadb]'

Data is stored in a local ./chroma_data directory next to this file.
"""

import guava
from guava import logging_utils
import os
from pathlib import Path

from guava.helpers.rag import DocumentQA, ChromaVectorStore

DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "docs"
DOCUMENTS = [p.read_text() for p in sorted(DOCS_DIR.glob("*.txt"))]

DOCUMENT_QA = DocumentQA(
    documents=DOCUMENTS,
    store=ChromaVectorStore(
        path=str(Path(__file__).parent / "chroma_data"),
        collection_name="policy_documents",
    ),
)


class ChromaPolicyQAController(guava.CallController):
    """Answers policy questions using ChromaDB retrieval and Gemini generation."""

    def __init__(self):
        super().__init__()
        self.read_script("Hello, how can I help you today?")
        self.accept_call()

    def on_question(self, question: str) -> str:
        return DOCUMENT_QA.ask(question)


if __name__ == "__main__":
    logging_utils.configure_logging()
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=ChromaPolicyQAController,
    )
