"""
Agentic RAG: routes questions to product-specific knowledge bases.

Maintains separate DocumentQA instances for auto, home, and life insurance
documents. An IntentRecognizer examines each question and dynamically picks
the most relevant knowledge base, preventing cross-contamination (e.g. auto
deductible info appearing when the caller asked about life insurance).
"""

import guava
import os
import logging
from guava import logging_utils
from pathlib import Path

from google import genai
from guava.helpers.genai import IntentRecognizer
from guava.helpers.rag import DocumentQA, LanceDBStore, VertexAIEmbedding, VertexAIGeneration

logger = logging.getLogger(__name__)

DOCS_DIR = Path(__file__).parent / "docs"


def load_documents(docs_dir: Path) -> list[str]:
    """Load all .txt files from a directory."""
    return [p.read_text() for p in sorted(docs_dir.glob("*.txt"))]


genai_client = genai.Client(vertexai=True)
embedding_model = VertexAIEmbedding(client=genai_client)
generation_model = VertexAIGeneration(client=genai_client)

# Build a separate DocumentQA per product line, each with its own LanceDB index.
DOCUMENT_QAS = {
    "auto insurance": DocumentQA(
        documents=load_documents(DOCS_DIR / "auto"),
        store=LanceDBStore(path=str(DOCS_DIR / "auto" / "lancedb_data"), embedding_model=embedding_model),
        generation_model=generation_model,
    ),
    "home insurance": DocumentQA(
        documents=load_documents(DOCS_DIR / "home"),
        store=LanceDBStore(path=str(DOCS_DIR / "home" / "lancedb_data"), embedding_model=embedding_model),
        generation_model=generation_model,
    ),
    "life insurance": DocumentQA(
        documents=load_documents(DOCS_DIR / "life"),
        store=LanceDBStore(path=str(DOCS_DIR / "life" / "lancedb_data"), embedding_model=embedding_model),
        generation_model=generation_model,
    ),
}

# Descriptions help the router understand what each knowledge base covers.
DESCRIPTIONS = {
    "auto insurance": "Car insurance, collision, comprehensive, liability, uninsured motorist, auto claims",
    "home insurance": "Homeowners insurance, dwelling coverage, personal property, endorsements, water backup",
    "life insurance": "Term life, whole life, death benefit, cash value, premiums by age, beneficiaries",
}


class MultiProductQAController(guava.CallController):
    """Routes each question to the best product-line knowledge base before answering."""

    def __init__(self):
        super().__init__()
        # The router uses the descriptions to classify which product line a question belongs to
        self.router = IntentRecognizer(DESCRIPTIONS, client=genai_client)
        self.read_script("Hello, how can I help you today?")
        self.accept_call()

    def on_question(self, question: str) -> str:
        # Classify which product line the question is about
        choice = self.router.classify(question)
        logger.info("Routed to '%s'", choice)
        # Answer from only the relevant knowledge base
        return DOCUMENT_QAS[choice].ask(question)


if __name__ == "__main__":
    logging_utils.configure_logging()
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=MultiProductQAController,
    )
