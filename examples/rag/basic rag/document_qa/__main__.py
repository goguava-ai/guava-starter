"""
Documents are uploaded to Guava at startup. Incoming caller questions are
answered by querying those documents via the server.

Environment variables:
    GUAVA_API_KEY      — Guava API key
    GUAVA_AGENT_NUMBER
"""

import guava
import os
from pathlib import Path

from guava.helpers.rag import DocumentQA
import logging                                                                                                                                                                                                                                                                                                                                
logging.basicConfig(level=logging.INFO)
DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "docs"
print(DOCS_DIR)
DOCUMENTS = [p.read_text() for p in sorted(DOCS_DIR.glob("*.txt"))]

DOCUMENT_QA = DocumentQA(documents=DOCUMENTS)


class PolicyQAController(guava.CallController):
    """Answers policy questions using the Guava server-side RAG API."""

    def __init__(self):
        super().__init__()
        self.read_script("Hello, how can I help you today?")
        self.accept_call()

    def on_question(self, question: str) -> str:
        return DOCUMENT_QA.ask(question)


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=PolicyQAController,
    )
