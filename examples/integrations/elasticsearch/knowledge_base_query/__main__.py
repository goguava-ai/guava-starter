import guava
import os
import logging
import requests

logging.basicConfig(level=logging.INFO)

ES_URL = os.environ["ELASTICSEARCH_URL"].rstrip("/")
KB_INDEX = os.environ.get("ELASTICSEARCH_KB_INDEX", "knowledge_base")


def get_headers() -> dict:
    return {
        "Authorization": f"ApiKey {os.environ['ELASTICSEARCH_API_KEY']}",
        "Content-Type": "application/json",
    }


def search_kb(question: str) -> list[dict]:
    body = {
        "query": {
            "multi_match": {
                "query": question,
                "fields": ["title^3", "content", "tags"],
                "type": "best_fields",
                "fuzziness": "AUTO",
            }
        },
        "size": 3,
        "_source": ["title", "content", "category", "url", "last_updated"],
        "highlight": {
            "fields": {
                "content": {"number_of_fragments": 1, "fragment_size": 300}
            }
        },
    }
    resp = requests.post(
        f"{ES_URL}/{KB_INDEX}/_search",
        headers=get_headers(),
        json=body,
        timeout=10,
    )
    resp.raise_for_status()
    hits = resp.json().get("hits", {}).get("hits", [])
    results = []
    for h in hits:
        source = h["_source"]
        highlight = h.get("highlight", {})
        snippet = highlight.get("content", [source.get("content", "")[:300]])[0]
        results.append({**source, "snippet": snippet})
    return results


class KnowledgeBaseQueryController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Apex Store",
            agent_name="Morgan",
            agent_purpose=(
                "to help Apex Store customers find answers to their questions using our knowledge base"
            ),
        )

        self.set_task(
            objective=(
                "A customer has called with a question. "
                "Collect their question, search the knowledge base, and read back the most relevant answer."
            ),
            checklist=[
                guava.Say(
                    "Welcome to Apex Store support. This is Morgan. What question can I help you with today?"
                ),
                guava.Field(
                    key="question",
                    field_type="text",
                    description="Ask for their question or what they need help with.",
                    required=True,
                ),
            ],
            on_complete=self.answer_question,
        )

        self.accept_call()

    def answer_question(self):
        question = self.get_field("question") or ""

        logging.info("Searching knowledge base for: %s", question)

        articles = []
        try:
            articles = search_kb(question)
            logging.info("Found %d knowledge base results", len(articles))
        except Exception as e:
            logging.error("Failed to search knowledge base: %s", e)

        if not articles:
            self.hangup(
                final_instructions=(
                    "Let the customer know we didn't find a specific article for that question. "
                    "Suggest they visit the Apex Store help center at support.apexstore.com, "
                    "or offer to connect them with a human agent. Thank them for calling."
                )
            )
            return

        top = articles[0]
        title = top.get("title", "Support Article")
        snippet = top.get("snippet", top.get("content", ""))[:500]
        url = top.get("url", "")

        self.hangup(
            final_instructions=(
                f"The best matching article is titled '{title}'. "
                f"Read the following excerpt to the customer: {snippet} "
                + (f"The full article is available at: {url}. " if url else "")
                + "Thank them for calling Apex Store."
            )
        )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=KnowledgeBaseQueryController,
    )
