# SDK conformance: guava-sdk 0.29.0 (2026-06-16)
"""
Cloud Vector DB RAG: Pinecone as a VectorStore with Pinecone Inference embeddings.

Demonstrates using Pinecone as a cloud-hosted vector database. Documents
are chunked and embedded with Pinecone Inference (multilingual-e5-large, 1024-dim),
then upserted to a Pinecone index. Queries are embedded the same way and
sent to Pinecone for nearest-neighbor search.

Unlike LanceDB (local), Pinecone is a managed service accessible from
anywhere without managing infrastructure. This pattern suits production
deployments where multiple agents share the same knowledge base.

Requires: pip install 'gridspace-guava[pinecone]'

Environment variables:
    PINECONE_API_KEY  — your Pinecone API key
"""

import argparse
import os
from pathlib import Path

import guava
from guava import logging_utils
from guava.helpers.pinecone import PineconeVectorStore
from guava.helpers.rag import DocumentQA

DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "docs"
DOCUMENTS = [p.read_text() for p in sorted(DOCS_DIR.glob("*.txt"))]

DOCUMENT_QA = DocumentQA(
    documents=DOCUMENTS,
    store=PineconeVectorStore(
        api_key=os.environ["PINECONE_API_KEY"],
        index_name="policy-documents",
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
