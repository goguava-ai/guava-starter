import guava
import os
import logging
import argparse
from datetime import datetime, timezone

from google.cloud import bigquery

logging.basicConfig(level=logging.INFO)

# Set this to your BigQuery table: "your_project.your_dataset.your_table"
BIGQUERY_TABLE = os.environ["BIGQUERY_TABLE"]


class NPSSurveyController(guava.CallController):
    def __init__(self, contact_name):
        super().__init__()
        self.contact_name = contact_name
        self.set_persona(
            organization_name="Acme Corp",
            agent_name="Alex",
            agent_purpose="to collect a brief NPS score from a recent customer",
        )
        self.reach_person(
            contact_full_name=self.contact_name,
            on_success=self.begin_survey,
            on_failure=self.hangup,
        )

    def begin_survey(self):
        self.set_task(
            objective=f"Conduct a brief NPS survey with {self.contact_name}.",
            checklist=[
                guava.Say(
                    f"Hi {self.contact_name}, this is Alex from Acme Corp. "
                    "I have just two quick questions about your recent experience — it'll take under a minute."
                ),
                guava.Field(
                    key="nps_score",
                    description="On a scale of 0 to 10, how likely are you to recommend us to a friend or colleague?",
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="reason",
                    description="Ask what's the main reason for their score. Optional — don't push if they'd rather not share.",
                    field_type="text",
                    required=False,
                ),
            ],
            on_complete=self.save_to_bigquery,
        )

    def save_to_bigquery(self):
        row = {
            "call_timestamp": datetime.now(timezone.utc).isoformat(),
            "contact_name": self.contact_name,
            "nps_score": self.get_field("nps_score"),
            "reason": self.get_field("reason"),
        }

        client = bigquery.Client()
        errors = client.insert_rows_json(BIGQUERY_TABLE, [row])
        if errors:
            logging.error("BigQuery insert failed: %s", errors)
        else:
            logging.info("Row written to BigQuery: %s", row)

        self.hangup(
            final_instructions="Thank them warmly for their feedback and wish them a great day."
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NPS survey → BigQuery → Looker Studio")
    parser.add_argument("phone", help="Phone number to call (E.164 format, e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Contact's full name")
    args = parser.parse_args()

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=NPSSurveyController(contact_name=args.name),
    )
