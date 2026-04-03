"""
Zendesk Help Center RAG: fetch articles via REST API, answer questions with Guava.

Pulls published Help Center articles from Zendesk Guide using the v2 REST API,
strips HTML from article bodies, and bulk-loads them into DocumentQA backed by
LanceDBStore. Each article is keyed by its Zendesk ID so re-running always
reflects the current state of your Help Center.

Requires:
    pip install requests

Environment variables:
    ZENDESK_SUBDOMAIN  — your Zendesk subdomain (e.g. "mycompany" for mycompany.zendesk.com)
    ZENDESK_EMAIL      — your Zendesk agent email address
    ZENDESK_API_TOKEN  — your Zendesk API token (Admin > Apps & Integrations > APIs > Zendesk API)
"""

import re
import os
import logging
from pathlib import Path

import requests
import guava
from guava.helpers.rag import DocumentQA, LanceDBStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Fetch the first 100 published articles from the Zendesk Help Center.
# For help centers with more articles, add cursor-based pagination using
# the "next_page" field in the response.
subdomain = os.environ["ZENDESK_SUBDOMAIN"]
response = requests.get(
    f"https://{subdomain}.zendesk.com/api/v2/help_center/articles",
    params={"per_page": 100},
    auth=(f"{os.environ['ZENDESK_EMAIL']}/token", os.environ["ZENDESK_API_TOKEN"]),
)
response.raise_for_status()
articles = response.json()["articles"]

IDS = [str(a["id"]) for a in articles]
DOCUMENTS = [
    f"{a['title']}\n{re.sub('<[^>]+>', '', a['body'] or '')}"
    for a in articles
]
logger.info("Loaded %d articles from Zendesk Help Center.", len(DOCUMENTS))

DOCUMENT_QA = DocumentQA(
    documents=DOCUMENTS,
    ids=IDS,
    store=LanceDBStore(path=str(Path(__file__).parent / "lancedb_data")),
)


class ZendeskController(guava.CallController):
    """Answers caller questions using Zendesk Help Center articles."""

    def __init__(self):
        super().__init__()
        self.read_script("Hello, how can I help you today?")
        self.accept_call()

    def on_question(self, question: str) -> str:
        return DOCUMENT_QA.ask(question)


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=ZendeskController,
    )
