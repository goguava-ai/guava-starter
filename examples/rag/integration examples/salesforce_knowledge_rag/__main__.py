"""
Salesforce Knowledge RAG: fetch articles via SOQL, answer questions with Guava.

Pulls all published Knowledge articles from Salesforce using simple-salesforce,
strips HTML from the body, and loads them into DocumentQA backed by LanceDBStore.

Unlike file-based RAG examples, documents are fetched live from Salesforce so
the knowledge base always reflects the current state of your Help Center.

Requires:
    pip install simple-salesforce

Environment variables:
    SALESFORCE_USERNAME       — Salesforce login username
    SALESFORCE_PASSWORD       — Salesforce login password
    SALESFORCE_SECURITY_TOKEN — Salesforce API security token
"""

import re
import os
import logging
from pathlib import Path

import guava
from simple_salesforce import Salesforce
from guava.helpers.rag import DocumentQA, LanceDBStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Connect to Salesforce and fetch all published Knowledge articles.
sf = Salesforce(
    username=os.environ["SALESFORCE_USERNAME"],
    password=os.environ["SALESFORCE_PASSWORD"],
    security_token=os.environ["SALESFORCE_SECURITY_TOKEN"],
)
result = sf.query(
    "SELECT Id, Title, Answer__c FROM Knowledge__kav "
    "WHERE PublishStatus = 'Online' AND Language = 'en_US'"
)
# Answer__c is the body field for the default FAQ article type.
# Adjust this field name to match your org's Knowledge article type.
IDS = [r["Id"] for r in result["records"]]
DOCUMENTS = [
    f"{r['Title']}\n{re.sub('<[^>]+>', '', r['Answer__c'] or '')}"
    for r in result["records"]
]
logger.info("Loaded %d articles from Salesforce Knowledge.", len(DOCUMENTS))

DOCUMENT_QA = DocumentQA(
    documents=DOCUMENTS,
    ids=IDS,
    store=LanceDBStore(path=str(Path(__file__).parent / "lancedb_data")),
)


class SalesforceKnowledgeController(guava.CallController):
    """Answers caller questions using Salesforce Knowledge articles."""

    def __init__(self):
        super().__init__()
        self.read_script("Hello, how can I help you today?")
        self.accept_call()

    def on_question(self, question: str) -> str:
        return DOCUMENT_QA.ask(question)


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=SalesforceKnowledgeController,
    )
