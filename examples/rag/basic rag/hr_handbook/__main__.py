"""
Employees call in to ask questions about company policy. Handbook documents
are uploaded to Guava at startup and queries are answered via the server-side
RAG API.

Environment variables:
    GUAVA_API_KEY      — Guava API key
    GUAVA_AGENT_NUMBER
"""

import guava
import os
import logging
from pathlib import Path

from guava.helpers.rag import DocumentQA

logging.basicConfig(level=logging.INFO)

DOCS_DIR = Path(__file__).resolve().parent / "docs"
DOCUMENTS = [p.read_text() for p in sorted(DOCS_DIR.glob("*.txt"))]

DOCUMENT_QA = DocumentQA(documents=DOCUMENTS)


class HRHandbookController(guava.CallController):
    """Answers employee policy questions using the company handbook."""

    def __init__(self):
        super().__init__()
        self.set_persona(
            organization_name="Meridian Technologies",
            agent_name="Jordan",
            agent_purpose=(
                "to answer employee questions about company policies, benefits, "
                "time-off procedures, and workplace guidelines"
            ),
        )
        self.read_script(
            "Hello, you've reached Meridian Technologies HR support. How can I help you today?"
        )
        self.accept_call()

    def on_question(self, question: str) -> str:
        return DOCUMENT_QA.ask(question)


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=HRHandbookController,
    )
