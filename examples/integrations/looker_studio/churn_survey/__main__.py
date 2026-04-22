import guava
import os
import logging
from guava import logging_utils
import argparse
from datetime import datetime, timezone

from google.cloud import bigquery


# Set this to your BigQuery table: "your_project.your_dataset.your_table"
BIGQUERY_TABLE = os.environ["BIGQUERY_TABLE"]


class ChurnSurveyController(guava.CallController):
    def __init__(self, contact_name: str, account_name: str):
        super().__init__()
        self.contact_name = contact_name
        self.account_name = account_name

        self.set_persona(
            organization_name="Acme Corp",
            agent_name="Morgan",
            agent_purpose=(
                "to understand why a customer recently cancelled "
                "and whether there's anything Acme Corp can do to improve"
            ),
        )

        self.reach_person(
            contact_full_name=self.contact_name,
            on_success=self.begin_survey,
            on_failure=self.hangup,
        )

    def begin_survey(self):
        self.set_task(
            objective=(
                f"Conduct a brief exit survey with {self.contact_name} from {self.account_name}. "
                "The goal is to understand why they cancelled and whether they'd ever return."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.contact_name}, this is Morgan from Acme Corp. "
                    "I saw that your account was recently cancelled and I wanted to reach out personally. "
                    "I have just a couple of questions — it'll take under two minutes and your feedback really matters to us."
                ),
                guava.Field(
                    key="primary_reason",
                    field_type="multiple_choice",
                    description="Ask what the main reason was for cancelling.",
                    choices=[
                        "price was too high",
                        "missing features I needed",
                        "switching to a competitor",
                        "not using it enough",
                        "technical issues",
                        "other",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="competitor_chosen",
                    field_type="text",
                    description=(
                        "If they mentioned switching to a competitor, ask which product they're moving to. "
                        "Otherwise skip this question."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="would_return",
                    field_type="multiple_choice",
                    description="Ask if they'd consider coming back in the future if things changed.",
                    choices=["yes, definitely", "maybe", "no"],
                    required=True,
                ),
                guava.Field(
                    key="feedback",
                    field_type="text",
                    description=(
                        "Ask if there's anything specific they'd want to see us improve. "
                        "Optional — keep it light."
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
            "account_name": self.account_name,
            "primary_reason": self.get_field("primary_reason"),
            "competitor_chosen": self.get_field("competitor_chosen"),
            "would_return": self.get_field("would_return"),
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
                "Thank them sincerely for their candid feedback. "
                "Let them know their input will be shared with the product team. "
                "If they seemed open to returning, mention they can always reach out at acmecorp.com. "
                "Wish them well."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(description="Churn exit survey → BigQuery → Looker Studio")
    parser.add_argument("phone", help="Phone number to call (E.164 format, e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Contact's full name")
    parser.add_argument("--account", required=True, help="Account or company name")
    args = parser.parse_args()

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=ChurnSurveyController(
            contact_name=args.name,
            account_name=args.account,
        ),
    )
