import guava
import os
import logging
from guava import logging_utils
from datetime import datetime, timezone

from google.cloud import bigquery


# Set this to your BigQuery table: "your_project.your_dataset.your_table"
BIGQUERY_TABLE = os.environ["BIGQUERY_TABLE"]

# Update with your event details
EVENT_NAME = os.environ.get("EVENT_NAME", "Acme Corp Annual Conference")
EVENT_DATE = os.environ.get("EVENT_DATE", "")


class EventRegistrationController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Acme Corp",
            agent_name="Sam",
            agent_purpose=f"to register callers for {EVENT_NAME}",
        )

        date_note = f" on {EVENT_DATE}" if EVENT_DATE else ""

        self.set_task(
            objective=(
                f"A caller wants to register for {EVENT_NAME}{date_note}. "
                "Collect their details and confirm their registration."
            ),
            checklist=[
                guava.Say(
                    f"Thanks for calling Acme Corp. I'm Sam. "
                    f"I'd be happy to get you registered for {EVENT_NAME}{date_note}. "
                    "Let me grab a few details."
                ),
                guava.Field(
                    key="full_name",
                    field_type="text",
                    description="Ask for their full name.",
                    required=True,
                ),
                guava.Field(
                    key="email",
                    field_type="text",
                    description="Ask for their email address — we'll send the confirmation there.",
                    required=True,
                ),
                guava.Field(
                    key="company",
                    field_type="text",
                    description="Ask what company they're with.",
                    required=False,
                ),
                guava.Field(
                    key="ticket_count",
                    field_type="integer",
                    description="Ask how many tickets they'd like (for themselves and any colleagues).",
                    required=True,
                ),
                guava.Field(
                    key="session_preference",
                    field_type="multiple_choice",
                    description="Ask which session time they'd prefer.",
                    choices=["morning session", "afternoon session", "evening session", "no preference"],
                    required=True,
                ),
                guava.Field(
                    key="dietary_requirements",
                    field_type="multiple_choice",
                    description="Ask if they have any dietary requirements for the catered lunch.",
                    choices=["none", "vegetarian", "vegan", "gluten-free", "other"],
                    required=True,
                ),
            ],
            on_complete=self.save_to_bigquery,
        )

        self.accept_call()

    def save_to_bigquery(self):
        row = {
            "call_timestamp": datetime.now(timezone.utc).isoformat(),
            "full_name": self.get_field("full_name"),
            "email": self.get_field("email"),
            "company": self.get_field("company"),
            "ticket_count": self.get_field("ticket_count"),
            "session_preference": self.get_field("session_preference"),
            "dietary_requirements": self.get_field("dietary_requirements"),
            "event_name": EVENT_NAME,
        }

        client = bigquery.Client()
        errors = client.insert_rows_json(BIGQUERY_TABLE, [row])
        if errors:
            logging.error("BigQuery insert failed: %s", errors)
        else:
            logging.info("Row written to BigQuery: %s", row)

        name = self.get_field("full_name") or "there"
        tickets = self.get_field("ticket_count") or 1
        session = self.get_field("session_preference") or "their preferred session"

        self.hangup(
            final_instructions=(
                f"Let {name} know they're registered for {EVENT_NAME}. "
                f"Confirm {tickets} ticket(s) and their session preference: {session}. "
                "Let them know a confirmation email with details will arrive shortly. "
                "Thank them and let them know we look forward to seeing them there."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=EventRegistrationController,
    )
