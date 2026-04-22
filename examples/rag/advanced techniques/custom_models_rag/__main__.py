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

import logging
import os
from pathlib import Path

import anthropic
import guava
import openai
from guava import logging_utils
from guava.helpers.lancedb import LanceDBStore
from guava.helpers.rag import (
    DocumentQA,
    EmbeddingModel,
    GenerationModel,
)

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
