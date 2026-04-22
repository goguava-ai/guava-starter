"""
Contextual Retrieval RAG: enriches chunks with Claude-generated context.

Implements Anthropic's Contextual Retrieval technique. Before indexing,
each chunk is sent to Claude alongside the full document. Claude generates
a short context summary (e.g. "This chunk discusses the water damage
exclusion in Section 4 of the homeowners policy") that is prepended to the
chunk. This extra context helps the retriever match ambiguous queries to
the right chunks.

Uses Anthropic prompt caching so the full document is processed once as a
cached system message, then each chunk gets a cheap follow-up call. The
enriched chunks are stored in LanceDB using Vertex AI embeddings, and
Gemini generates the final answer.

Requires ANTHROPIC_API_KEY in addition to the standard Guava credentials.
"""

import guava
import os
import logging
from guava import logging_utils
from pathlib import Path

import anthropic
from google import genai
from guava.helpers.lancedb import LanceDBStore
from guava.helpers.vertexai import VertexAIEmbedding
from guava.helpers.rag import chunk_document

logger = logging.getLogger(__name__)

DOCS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "docs"

_DEFAULT_INSTRUCTIONS = (
    "You are a virtual contact center agent. Your task is to answer questions "
    "using ONLY the provided supporting document excerpts. If the answer is not "
    "in the provided context, say so. Just answer the question — do not offer "
    "any follow-ups."
)


def contextualize_chunks(
    client: anthropic.Anthropic, document: str, chunks: list[str],
) -> list[str]:
    """Prepend a Claude-generated context summary to each chunk.

    The full document is passed as a cached system message so it's only
    processed once. Each chunk then gets a short contextual description
    prepended to improve retrieval accuracy.
    """
    contextualized: list[str] = []
    for i, chunk in enumerate(chunks):
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            # The document is cached — subsequent chunks reuse the same cached input
            system=[{
                "type": "text",
                "text": f"<document>\n{document}\n</document>",
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{
                "role": "user",
                "content": (
                    f"<chunk>\n{chunk}\n</chunk>\n\n"
                    "Please give a short succinct context to situate this chunk "
                    "within the overall document for the purposes of improving "
                    "search retrieval of the chunk. Answer only with the succinct "
                    "context and nothing else."
                ),
            }],
        )
        # Prepend the generated context to the original chunk text
        contextualized.append(f"{response.content[0].text}\n\n{chunk}")
        logger.info("Contextualized chunk %d/%d", i + 1, len(chunks))
    return contextualized


# Build the contextualized index at startup:
# 1. Split each document into chunks
# 2. Enrich each chunk with Claude-generated context
# 3. Embed and store the enriched chunks in LanceDB via Vertex AI
genai_client = genai.Client(vertexai=True)
anthropic_client = anthropic.Anthropic()
store = LanceDBStore(
    path=str(Path(__file__).parent / "lancedb_data"),
    embedding_model=VertexAIEmbedding(client=genai_client),
)

if store.count() == 0:
    logger.info("First run — contextualizing and indexing documents...")
    all_chunks: list[str] = []
    for doc_path in sorted(DOCS_DIR.glob("*.txt")):
        doc = doc_path.read_text()
        raw = chunk_document(doc)
        all_chunks.extend(contextualize_chunks(anthropic_client, doc, raw))
    store.add_texts(all_chunks)
    logger.info("Contextual index ready (%d chunks).", len(all_chunks))
else:
    logger.info("Loaded existing contextual index (%d chunks).", store.count())

agent = guava.Agent()


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.read_script("Hello, how can I help you today?")


@agent.on_question
def on_question(call: guava.Call, question: str) -> str:
    chunks = store.search(question, k=10)
    context = "\n\n---\n\n".join(chunks)
    response = genai_client.models.generate_content(
        model="gemini-2.5-flash",
        contents=f"Context:\n{context}\n\nQuestion: {question}",
        config={"system_instruction": _DEFAULT_INSTRUCTIONS},
    )
    return response.text or ""


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
