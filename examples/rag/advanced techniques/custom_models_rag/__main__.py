"""
Custom Models RAG: plug in any embedding and generation model.

Demonstrates the full extensibility of DocumentQA by replacing both the
embedding model (OpenAI text-embedding-3-large) and the generation model
(Anthropic Claude) with third-party implementations.

Any object that subclasses EmbeddingModel or GenerationModel can be passed
in — no Guava-specific API keys are required for the custom models themselves.

Requires:
    pip install openai anthropic

Environment variables:
    OPENAI_API_KEY    — OpenAI API key for embeddings
    ANTHROPIC_API_KEY — Anthropic API key for answer generation
"""

import guava
import os
import logging
from pathlib import Path

import anthropic
import openai

from guava.helpers.rag import (
    DocumentQA,
    EmbeddingModel,
    GenerationModel,
    LanceDBStore,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "docs"
DOCUMENTS = [p.read_text() for p in sorted(DOCS_DIR.glob("*.txt"))]


class OpenAIEmbedding(EmbeddingModel):
    """Embedding via OpenAI's text-embedding-3-large model (3072 dims)."""

    def __init__(self, model: str = "text-embedding-3-large"):
        self._client = openai.OpenAI()
        self._model = model

    def ndims(self) -> int:
        return 3072

    def embed(self, texts: list[str]) -> list[list[float]]:
        response = self._client.embeddings.create(input=texts, model=self._model)
        return [e.embedding for e in response.data]


class ClaudeGeneration(GenerationModel):
    """Answer generation via Anthropic Claude."""

    def __init__(self, model: str = "claude-haiku-4-5-20251001"):
        self._client = anthropic.Anthropic()
        self._model = model

    def generate(self, prompt: str, *, system_instruction: str | None = None) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=system_instruction or "",
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text


DOCUMENT_QA = DocumentQA(
    documents=DOCUMENTS,
    store=LanceDBStore(
        path=str(Path(__file__).parent / "lancedb_data"),
        embedding_model=OpenAIEmbedding(),
    ),
    generation_model=ClaudeGeneration(),
)


class CustomModelsPolicyQAController(guava.CallController):
    """Answers policy questions using OpenAI embeddings and Claude generation."""

    def __init__(self):
        super().__init__()
        self.read_script("Hello, how can I help you today?")
        self.accept_call()

    def on_question(self, question: str) -> str:
        return DOCUMENT_QA.ask(question)


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=CustomModelsPolicyQAController,
    )
