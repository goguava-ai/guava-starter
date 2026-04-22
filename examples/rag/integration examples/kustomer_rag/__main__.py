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

import logging
import os
from pathlib import Path

import guava
import requests
from google import genai
from guava import logging_utils
from guava.helpers.lancedb import LanceDBStore
from guava.helpers.rag import DocumentQA
from guava.helpers.vertexai import VertexAIEmbedding

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

genai_client = genai.Client(vertexai=True)
DOCUMENT_QA = DocumentQA(
    documents=DOCUMENTS,
    ids=IDS,
    store=LanceDBStore(
        path=str(Path(__file__).parent / "lancedb_data"),
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
