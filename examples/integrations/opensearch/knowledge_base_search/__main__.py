import guava
import os
import logging
from guava import logging_utils
from opensearchpy import OpenSearch, NotFoundError


OPENSEARCH_HOST = os.environ["OPENSEARCH_HOST"]
OPENSEARCH_PORT = int(os.environ.get("OPENSEARCH_PORT", "443"))
OPENSEARCH_USER = os.environ["OPENSEARCH_USER"]
OPENSEARCH_PASSWORD = os.environ["OPENSEARCH_PASSWORD"]
KB_INDEX = os.environ.get("OPENSEARCH_KB_INDEX", "knowledge-base")

client = OpenSearch(
    hosts=[{"host": OPENSEARCH_HOST, "port": OPENSEARCH_PORT}],
    http_auth=(OPENSEARCH_USER, OPENSEARCH_PASSWORD),
    use_ssl=True,
    verify_certs=True,
)


def search_knowledge_base(query: str, top_k: int = 3) -> list[dict]:
    """Full-text search across the knowledge base index. Returns top matching articles."""
    body = {
        "size": top_k,
        "query": {
            "multi_match": {
                "query": query,
                "fields": ["title^2", "content", "tags"],
                "type": "best_fields",
                "fuzziness": "AUTO",
            }
        },
        "_source": ["title", "content", "category", "url"],
    }
    try:
        response = client.search(index=KB_INDEX, body=body)
        return [hit["_source"] for hit in response["hits"]["hits"]]
    except NotFoundError:
        logging.warning("Knowledge base index '%s' not found.", KB_INDEX)
        return []


def format_kb_results(articles: list[dict]) -> str:
    if not articles:
        return ""
    parts = []
    for i, article in enumerate(articles, 1):
        title = article.get("title", f"Article {i}")
        content = (article.get("content") or "")[:300].rstrip()
        parts.append(f"{i}. {title}: {content}")
    return " | ".join(parts)


agent = guava.Agent(
    name="Quinn",
    organization="Novus Technologies",
    purpose=(
        "to answer customer questions about Novus Technologies products and services "
        "by searching our knowledge base"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "search_and_answer",
        objective=(
            "A customer has called with a question. Understand their question, search "
            "the knowledge base, and answer using the results. If the KB doesn't have "
            "a relevant answer, offer to escalate."
        ),
        checklist=[
            guava.Say(
                "Thanks for calling Novus Technologies. This is Quinn. "
                "I'm here to help — what's your question today?"
            ),
            guava.Field(
                key="customer_question",
                field_type="text",
                description=(
                    "Listen carefully to the customer's question. Ask any clarifying "
                    "questions needed to understand exactly what they're looking for. "
                    "Capture a clear, complete version of their question."
                ),
                required=True,
            ),
        ],
    )


@agent.on_task_complete("search_and_answer")
def on_done(call: guava.Call) -> None:
    question = call.get_field("customer_question") or ""
    logging.info("Searching knowledge base for: %s", question)

    try:
        articles = search_knowledge_base(question)
    except Exception as e:
        logging.error("Knowledge base search failed: %s", e)
        articles = []

    if not articles:
        call.hangup(
            final_instructions=(
                "Let the customer know you weren't able to find a specific answer in "
                "your knowledge base for their question. Apologize and offer to connect "
                "them with a specialist who can help, or suggest they check the support "
                "portal at novustech.com/support. Be empathetic and helpful."
            )
        )
        return

    kb_summary = format_kb_results(articles)
    logging.info("Found %d KB articles for query: %s", len(articles), question)

    call.hangup(
        final_instructions=(
            f"Using the following knowledge base results, answer the customer's question: "
            f"'{question}'. Knowledge base content: {kb_summary}. "
            "Summarize the answer conversationally — do not read the raw text verbatim. "
            "If only partially relevant results were found, answer as best you can and "
            "offer to escalate or direct them to the support portal for more detail. "
            "Thank them for calling Novus Technologies."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
