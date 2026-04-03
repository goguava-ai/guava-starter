"""
Customers call in with questions about their Apex BrewMaster Pro coffee maker.
Product documents are uploaded to Guava at startup and queries are answered via
the server-side RAG API.

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


class ProductSupportController(guava.CallController):
    """Answers customer questions using the product manual and troubleshooting guide."""

    def __init__(self):
        super().__init__()
        self.set_persona(
            organization_name="Apex Home Appliances",
            agent_name="Casey",
            agent_purpose=(
                "to help customers with setup, operation, and troubleshooting questions "
                "for the Apex BrewMaster Pro coffee maker"
            ),
        )
        self.read_script(
            "Thank you for calling Apex Home Appliances support. How can I help you today?"
        )
        self.accept_call()

    def on_question(self, question: str) -> str:
        return DOCUMENT_QA.ask(question)


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=ProductSupportController,
    )
