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


class KnowledgeBaseSearchController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Novus Technologies",
            agent_name="Quinn",
            agent_purpose=(
                "to answer customer questions about Novus Technologies products and services "
                "by searching our knowledge base"
            ),
        )

        self.set_task(
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
            on_complete=self.search_and_answer,
        )

        self.accept_call()

    def search_and_answer(self):
        question = self.get_field("customer_question") or ""
        logging.info("Searching knowledge base for: %s", question)

        try:
            articles = search_knowledge_base(question)
        except Exception as e:
            logging.error("Knowledge base search failed: %s", e)
            articles = []

        if not articles:
            self.hangup(
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

        self.hangup(
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
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=KnowledgeBaseSearchController,
    )
