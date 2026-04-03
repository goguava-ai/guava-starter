"""
Kustomer Knowledge Base RAG: fetch articles via REST API, answer questions with Guava.

Pulls published knowledge base articles from Kustomer using the v3 API and
loads them into DocumentQA backed by LanceDBStore. Documents are fetched fresh
at startup so the knowledge base always reflects your current Kustomer content.

Requires:
    pip install requests

Environment variables:
    KUSTOMER_API_KEY — Kustomer API key (Settings > Security > API Keys)
"""

import os
import logging
from pathlib import Path

import requests
import guava
from guava.helpers.rag import DocumentQA, LanceDBStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Fetch published articles from the Kustomer knowledge base.
response = requests.get(
    "https://api.kustomerapp.com/p/v3/kb/articles",
    headers={"Authorization": f"Bearer {os.environ['KUSTOMER_API_KEY']}"},
)
response.raise_for_status()
articles = response.json()["data"]

IDS = [str(a["id"]) for a in articles]
DOCUMENTS = [
    f"{a['title']}\n{a.get('content', '')}"
    for a in articles
]
logger.info("Loaded %d articles from Kustomer.", len(DOCUMENTS))

DOCUMENT_QA = DocumentQA(
    documents=DOCUMENTS,
    ids=IDS,
    store=LanceDBStore(path=str(Path(__file__).parent / "lancedb_data")),
)


class KustomerController(guava.CallController):
    """Answers caller questions using Kustomer knowledge base articles."""

    def __init__(self):
        super().__init__()
        self.read_script("Hello, how can I help you today?")
        self.accept_call()

    def on_question(self, question: str) -> str:
        return DOCUMENT_QA.ask(question)


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=KustomerController,
    )
