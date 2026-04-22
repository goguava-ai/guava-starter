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
from guava import logging_utils
from pathlib import Path

from guava.helpers.rag import DocumentQA


DOCS_DIR = Path(__file__).resolve().parent / "docs"
DOCUMENTS = [p.read_text() for p in sorted(DOCS_DIR.glob("*.txt"))]

DOCUMENT_QA = DocumentQA(documents=DOCUMENTS)

agent = guava.Agent(
    name="Jordan",
    organization="Meridian Technologies",
    purpose=(
        "to answer employee questions about company policies, benefits, "
        "time-off procedures, and workplace guidelines"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.read_script(
        "Hello, you've reached Meridian Technologies HR support. How can I help you today?"
    )


@agent.on_question
def on_question(call: guava.Call, question: str) -> str:
    return DOCUMENT_QA.ask(question)


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
