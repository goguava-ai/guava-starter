import guava
import os
import logging
from guava import logging_utils
import argparse
from datetime import datetime, timezone

from google.cloud import bigquery


# Set this to your BigQuery table: "your_project.your_dataset.your_table"
BIGQUERY_TABLE = os.environ["BIGQUERY_TABLE"]


class WinLossSurveyController(guava.CallController):
    def __init__(self, contact_name: str, company_name: str, deal_outcome: str):
        super().__init__()
        self.contact_name = contact_name
        self.company_name = company_name
        self.deal_outcome = deal_outcome  # 'won' or 'lost'

        self.set_persona(
            organization_name="Acme Corp",
            agent_name="Blake",
            agent_purpose=(
                "to understand the factors behind a recently closed deal "
                "and share that insight with the sales and product teams"
            ),
        )

        self.reach_person(
            contact_full_name=self.contact_name,
            on_success=self.begin_survey,
            on_failure=self.hangup,
        )

    def begin_survey(self):
        if self.deal_outcome == "won":
            intro = (
                f"Hi {self.contact_name}, this is Blake from Acme Corp. "
                "I'm so glad you chose to work with us. "
                "I have just a couple of quick questions about what made the difference in your decision — "
                "it helps us understand what's working well."
            )
            objective = f"Understand why {self.contact_name} at {self.company_name} chose Acme Corp."
        else:
            intro = (
                f"Hi {self.contact_name}, this is Blake from Acme Corp. "
                "I know you recently evaluated us and decided to go in a different direction. "
                "I completely respect that — I just wanted to ask two quick questions so we can keep improving."
            )
            objective = f"Understand why {self.contact_name} at {self.company_name} did not choose Acme Corp."

        self.set_task(
            objective=objective,
            checklist=[
                guava.Say(intro),
                guava.Field(
                    key="main_reason",
                    field_type="multiple_choice",
                    description=(
                        "Ask what the most important factor was in their decision. "
                        + ("Frame positively since this is a won deal." if self.deal_outcome == "won" else "")
                    ),
                    choices=[
                        "price and value",
                        "features and functionality",
                        "ease of use",
                        "quality of support",
                        "company reputation or trust",
                        "integration with existing tools",
                        "other",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="runner_up",
                    field_type="text",
                    description=(
                        "Ask which other solution they considered before making their decision. "
                        "Optional — they may not want to share."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="feedback",
                    field_type="text",
                    description=(
                        "Ask if there's any other feedback they'd be willing to share — "
                        "something that stood out positively or that we could improve. Optional."
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
            "company_name": self.company_name,
            "deal_outcome": self.deal_outcome,
            "main_reason": self.get_field("main_reason"),
            "runner_up": self.get_field("runner_up"),
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
                f"Thank {self.contact_name} for sharing their perspective. "
                + (
                    "Let them know you're excited to work together and their account team will be in touch soon. "
                    if self.deal_outcome == "won"
                    else "Let them know you appreciate the candid feedback and wish them all the best. "
                    "Mention they're always welcome to reach out if things change. "
                )
                + "Wish them a great day."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(description="Win/loss survey → BigQuery → Looker Studio")
    parser.add_argument("phone", help="Phone number to call (E.164 format, e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Contact's full name")
    parser.add_argument("--company", required=True, help="Company name")
    parser.add_argument(
        "--outcome",
        required=True,
        choices=["won", "lost"],
        help="Whether this deal was won or lost",
    )
    args = parser.parse_args()

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=WinLossSurveyController(
            contact_name=args.name,
            company_name=args.company,
            deal_outcome=args.outcome,
        ),
    )
