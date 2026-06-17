# SDK conformance: guava-sdk 0.29.0 (2026-06-16)
"""
Employees call in to ask questions about company policy. Handbook documents
are uploaded to Guava at startup and queries are answered via the server-side
RAG API.

Environment variables:
    GUAVA_API_KEY      — Guava API key
    GUAVA_AGENT_NUMBER
"""

import argparse
from pathlib import Path

import guava
from guava import logging_utils
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

    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--phone", metavar="PHONE_NUMBER", nargs="?", const="", help="Listen for phone calls."
    )
    group.add_argument(
        "--webrtc", metavar="WEBRTC_CODE", nargs="?", const="", help="Listen on a WebRTC code."
    )
    group.add_argument("--local", action="store_true", help="Start a local call.")
    group.add_argument("--sip", metavar="SIP_CODE", help="Listen on a SIP code \'guavasip-...\'.")
    args = parser.parse_args()

    if args.phone is not None:
        agent.listen_phone(args.phone)
    elif args.webrtc is not None:
        agent.listen_webrtc(args.webrtc or None)
    elif args.sip:
        agent.listen_sip(args.sip)
    else:
        agent.call_local()
