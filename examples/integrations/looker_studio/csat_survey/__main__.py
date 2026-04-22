import guava
import os
import logging
from guava import logging_utils
import argparse
from datetime import datetime, timezone

from google.cloud import bigquery


# Set this to your BigQuery table: "your_project.your_dataset.your_table"
BIGQUERY_TABLE = os.environ["BIGQUERY_TABLE"]


class CSATSurveyController(guava.CallController):
    def __init__(self, contact_name: str, ticket_id: str):
        super().__init__()
        self.contact_name = contact_name
        self.ticket_id = ticket_id

        self.set_persona(
            organization_name="Acme Corp",
            agent_name="Jordan",
            agent_purpose="to collect a quick satisfaction rating after a recent support interaction",
        )

        self.reach_person(
            contact_full_name=self.contact_name,
            on_success=self.begin_survey,
            on_failure=self.hangup,
        )

    def begin_survey(self):
        self.set_task(
            objective=f"Collect a brief CSAT survey from {self.contact_name} about their recent support experience.",
            checklist=[
                guava.Say(
                    f"Hi {self.contact_name}, this is Jordan from Acme Corp. "
                    "I'm following up on your recent support ticket — I just have two quick questions."
                ),
                guava.Field(
                    key="satisfaction_score",
                    field_type="integer",
                    description=(
                        "Ask: on a scale of 1 to 5, how satisfied were you with the support you received? "
                        "1 is very dissatisfied, 5 is very satisfied."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="was_issue_resolved",
                    field_type="multiple_choice",
                    description="Ask whether their issue was fully resolved.",
                    choices=["yes, fully resolved", "partially resolved", "no, still unresolved"],
                    required=True,
                ),
                guava.Field(
                    key="feedback",
                    field_type="text",
                    description=(
                        "Ask if there's anything they'd like to share about the experience. "
                        "Optional — don't push if they'd rather not."
                    ),
                    required=False,
                ),
            ],
            on_complete=self.save_to_bigquery,
        )

    def save_to_bigquery(self):
        row = {
            "call_timestamp": datetime.now(timezone.utc).isoformat(),
            "contact_name": self.contact_name,
            "ticket_id": self.ticket_id,
            "satisfaction_score": self.get_field("satisfaction_score"),
            "was_issue_resolved": self.get_field("was_issue_resolved"),
            "feedback": self.get_field("feedback"),
        }

        client = bigquery.Client()
        errors = client.insert_rows_json(BIGQUERY_TABLE, [row])
        if errors:
            logging.error("BigQuery insert failed: %s", errors)
        else:
            logging.info("Row written to BigQuery: %s", row)

        self.hangup(
            final_instructions=(
                "Thank them for taking the time to share their feedback. "
                "If their issue was not fully resolved, let them know a specialist "
                "will follow up by email. Wish them a great day."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(description="CSAT survey → BigQuery → Looker Studio")
    parser.add_argument("phone", help="Phone number to call (E.164 format, e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Contact's full name")
    parser.add_argument("--ticket-id", required=True, help="Support ticket ID")
    args = parser.parse_args()

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=CSATSurveyController(
            contact_name=args.name,
            ticket_id=args.ticket_id,
        ),
    )
