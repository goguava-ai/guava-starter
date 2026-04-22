"""
Customers call in with questions about their Apex BrewMaster Pro coffee maker.
Product documents are uploaded to Guava at startup and queries are answered via
the server-side RAG API.

Environment variables:
    GUAVA_API_KEY      — Guava API key
    GUAVA_AGENT_NUMBER
"""

import logging
import os
from pathlib import Path

import guava
from guava import logging_utils
from guava.helpers.rag import DocumentQA

DOCS_DIR = Path(__file__).resolve().parent / "docs"
DOCUMENTS = [p.read_text() for p in sorted(DOCS_DIR.glob("*.txt"))]

DOCUMENT_QA = DocumentQA(documents=DOCUMENTS)

agent = guava.Agent(
    name="Casey",
    organization="Apex Home Appliances",
    purpose=(
        "to help customers with setup, operation, and troubleshooting questions "
        "for the Apex BrewMaster Pro coffee maker"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.read_script(
        "Thank you for calling Apex Home Appliances support. How can I help you today?"
    )


@agent.on_question
def on_question(call: guava.Call, question: str) -> str:
    return DOCUMENT_QA.ask(question)


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
