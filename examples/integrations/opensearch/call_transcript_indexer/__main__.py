import guava
import os
import logging
from datetime import datetime, timezone
from opensearchpy import OpenSearch

logging.basicConfig(level=logging.INFO)

OPENSEARCH_HOST = os.environ["OPENSEARCH_HOST"]
OPENSEARCH_PORT = int(os.environ.get("OPENSEARCH_PORT", "443"))
OPENSEARCH_USER = os.environ["OPENSEARCH_USER"]
OPENSEARCH_PASSWORD = os.environ["OPENSEARCH_PASSWORD"]
CALLS_INDEX = os.environ.get("OPENSEARCH_CALLS_INDEX", "call-records")

client = OpenSearch(
    hosts=[{"host": OPENSEARCH_HOST, "port": OPENSEARCH_PORT}],
    http_auth=(OPENSEARCH_USER, OPENSEARCH_PASSWORD),
    use_ssl=True,
    verify_certs=True,
)


def index_call_record(record: dict) -> str:
    """Index a call record document and return the assigned document ID."""
    response = client.index(
        index=CALLS_INDEX,
        body=record,
    )
    return response.get("_id", "")


class CallTranscriptIndexerController(guava.CallController):
    """
    Inbound agent that handles a customer interaction and indexes the structured
    call outcome into OpenSearch for downstream reporting and search.
    """

    def __init__(self):
        super().__init__()
        self._call_start = datetime.now(timezone.utc)

        self.set_persona(
            organization_name="Clearline Financial",
            agent_name="Morgan",
            agent_purpose=(
                "to help Clearline Financial customers with account inquiries and log "
                "each interaction in our records system"
            ),
        )

        self.set_task(
            objective=(
                "Handle the customer's inquiry. After the call, index a structured record "
                "of the interaction — caller info, topic, outcome, and sentiment — into OpenSearch."
            ),
            checklist=[
                guava.Say(
                    "Thank you for calling Clearline Financial. This is Morgan. "
                    "How can I help you today?"
                ),
                guava.Field(
                    key="caller_name",
                    field_type="text",
                    description="Ask for the caller's full name.",
                    required=True,
                ),
                guava.Field(
                    key="account_number",
                    field_type="text",
                    description=(
                        "Ask for their account number for verification. "
                        "If they don't have it handy, ask for their date of birth and ZIP code instead."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="inquiry_topic",
                    field_type="multiple_choice",
                    description="Ask what they're calling about today.",
                    choices=[
                        "account balance",
                        "recent transactions",
                        "payment due date",
                        "dispute a charge",
                        "update contact information",
                        "loan inquiry",
                        "other",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="inquiry_detail",
                    field_type="text",
                    description=(
                        "Listen to and address their inquiry. Capture a clear summary "
                        "of what they asked and what was resolved or communicated."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="resolution",
                    field_type="multiple_choice",
                    description="How was the call resolved?",
                    choices=[
                        "resolved — answered fully",
                        "escalated to human agent",
                        "caller will follow up",
                        "unresolved — system issue",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="caller_sentiment",
                    field_type="multiple_choice",
                    description=(
                        "Based on the conversation, how would you characterize the caller's overall sentiment?"
                    ),
                    choices=["positive", "neutral", "frustrated", "very upset"],
                    required=True,
                ),
            ],
            on_complete=self.index_and_close,
        )

        self.accept_call()

    def index_and_close(self):
        name = self.get_field("caller_name") or "Unknown"
        account = self.get_field("account_number") or ""
        topic = self.get_field("inquiry_topic") or "other"
        detail = self.get_field("inquiry_detail") or ""
        resolution = self.get_field("resolution") or "resolved — answered fully"
        sentiment = self.get_field("caller_sentiment") or "neutral"

        call_duration_seconds = int(
            (datetime.now(timezone.utc) - self._call_start).total_seconds()
        )

        record = {
            "caller_name": name,
            "account_number": account,
            "inquiry_topic": topic,
            "inquiry_detail": detail,
            "resolution": resolution,
            "caller_sentiment": sentiment,
            "call_timestamp": self._call_start.isoformat(),
            "call_duration_seconds": call_duration_seconds,
            "agent": "Morgan",
            "channel": "voice",
            "organization": "Clearline Financial",
        }

        logging.info(
            "Indexing call record for %s — topic: %s, resolution: %s, sentiment: %s",
            name, topic, resolution, sentiment,
        )

        try:
            doc_id = index_call_record(record)
            logging.info("Call record indexed in OpenSearch with ID: %s", doc_id)
        except Exception as e:
            logging.error("Failed to index call record: %s", e)

        escalated = "escalated" in resolution
        self.hangup(
            final_instructions=(
                f"Wrap up the call with {name} appropriately. "
                + (
                    "Let them know a specialist will be in touch shortly to continue assisting them. "
                    if escalated
                    else "Thank them for calling and wish them a great day. "
                )
                + "Keep the closing warm and professional."
            )
        )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=CallTranscriptIndexerController,
    )
