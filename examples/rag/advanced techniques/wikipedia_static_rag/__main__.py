"""
Static Wikipedia RAG: fetches articles at startup, indexes with Vertex AI embeddings.

Fetches a fixed set of Wikipedia articles about insurance concepts at startup,
embeds them into a LanceDBStore via Vertex AI, and answers caller questions
using DocumentQA. No API key is needed for Wikipedia — only the embedding
and answer generation use Vertex AI.

Good for supplementing domain-specific docs with general background
knowledge (e.g. "What is subrogation?" or "How does flood insurance work?").
"""

import guava
import os
import logging
from guava import logging_utils

import httpx
from google import genai
from guava.helpers.rag import DocumentQA
from guava.helpers.lancedb import LanceDBStore
from guava.helpers.vertexai import VertexAIEmbedding, VertexAIGeneration

logger = logging.getLogger(__name__)


def fetch_wikipedia_article(http: httpx.Client, title: str) -> str:
    """Fetch the plain-text extract of a Wikipedia article by title."""
    resp = http.get(
        "https://en.wikipedia.org/w/api.php",
        params={"action": "query", "titles": title, "prop": "extracts",
                "explaintext": "1", "format": "json"},
    )
    resp.raise_for_status()
    for page in resp.json().get("query", {}).get("pages", {}).values():
        if page.get("extract"):
            return page["extract"]
    return ""


# Articles to fetch and index at startup.
WIKI_ARTICLES = [
    "Homeowner's insurance", "Flood insurance", "Earthquake insurance",
    "Insurance policy", "Deductible", "Actual cash value",
    "Replacement cost", "Subrogation",
]

# Fetch all articles, then build a single DocumentQA over their content.
http = httpx.Client(timeout=15.0, headers={"User-Agent": "Mozilla/5.0 (compatible; python-httpx/0.27)"})
documents = [text for title in WIKI_ARTICLES if (text := fetch_wikipedia_article(http, title))]
logger.info("Fetched %d Wikipedia articles.", len(documents))

genai_client = genai.Client(vertexai=True)
DOCUMENT_QA = DocumentQA(
    documents=documents,
    store=LanceDBStore(embedding_model=VertexAIEmbedding(client=genai_client)),
    generation_model=VertexAIGeneration(client=genai_client),
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
