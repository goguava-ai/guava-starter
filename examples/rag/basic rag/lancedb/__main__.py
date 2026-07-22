# SDK conformance: guava-sdk 0.34.0 (2026-07-21)
"""
Basic RAG: document QA over policy files using LanceDB.

Loads policy documents from docs/, indexes them into a LanceDBStore,
and answers every caller question via DocumentQA.
This is the simplest RAG pattern — a single retriever over a static document set.
"""

import argparse
import logging
from pathlib import Path

import guava
from google import genai
from guava import logging_utils
from guava.helpers.lancedb import LanceDBStore
from guava.helpers.rag import DocumentQA
from guava.helpers.vertexai import VertexAIEmbedding, VertexAIGeneration

logger = logging.getLogger(__name__)

# Load all policy documents and build the vector index at startup.
# DocumentQA is shared across all calls so documents are only embedded once.
DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "docs"
DOCUMENTS = [p.read_text() for p in sorted(DOCS_DIR.glob("*.txt"))]

genai_client = genai.Client(vertexai=True)
DOCUMENT_QA = DocumentQA(
    documents=DOCUMENTS,
    store=LanceDBStore(
        path=str(Path(__file__).parent / "lancedb_data"),
        embedding_model=VertexAIEmbedding(client=genai_client),
    ),
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
