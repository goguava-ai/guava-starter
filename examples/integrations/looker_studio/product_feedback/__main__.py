import guava
import os
import logging
import argparse
from datetime import datetime, timezone

from google.cloud import bigquery

logging.basicConfig(level=logging.INFO)

# Set this to your BigQuery table: "your_project.your_dataset.your_table"
BIGQUERY_TABLE = os.environ["BIGQUERY_TABLE"]


class ProductFeedbackController(guava.CallController):
    def __init__(self, contact_name: str, product_name: str):
        super().__init__()
        self.contact_name = contact_name
        self.product_name = product_name

        self.set_persona(
            organization_name="Acme Corp",
            agent_name="Taylor",
            agent_purpose=(
                f"to collect honest feedback from a customer about their experience with {product_name}"
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
                f"Collect product feedback from {self.contact_name} "
                f"about their experience with {self.product_name}."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.contact_name}, this is Taylor from Acme Corp. "
                    f"I'm reaching out to hear how you're finding {self.product_name}. "
                    "It'll take under two minutes — your feedback goes directly to our product team."
                ),
                guava.Field(
                    key="product_rating",
                    field_type="integer",
                    description=(
                        f"Ask them to rate {self.product_name} overall on a scale of 1 to 5, "
                        "where 1 is very poor and 5 is excellent."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="usage_frequency",
                    field_type="multiple_choice",
                    description="Ask how often they're using the product.",
                    choices=[
                        "every day",
                        "a few times a week",
                        "about once a week",
                        "a few times a month",
                        "haven't used it yet",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="top_feature",
                    field_type="text",
                    description=(
                        "Ask what their favourite feature or aspect of the product is. "
                        "Optional — skip if they'd rather not share."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="improvement_suggestion",
                    field_type="text",
                    description=(
                        "Ask if there's one thing they'd change or improve. "
                        "Optional — keep it conversational."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="would_recommend",
                    field_type="multiple_choice",
                    description="Ask if they'd recommend the product to a colleague or friend.",
                    choices=["yes, definitely", "probably yes", "not sure", "probably not", "definitely not"],
                    required=True,
                ),
            ],
            on_complete=self.save_to_bigquery,
        )

    def save_to_bigquery(self):
        row = {
            "call_timestamp": datetime.now(timezone.utc).isoformat(),
            "contact_name": self.contact_name,
            "product_name": self.product_name,
            "product_rating": self.get_field("product_rating"),
            "usage_frequency": self.get_field("usage_frequency"),
            "top_feature": self.get_field("top_feature"),
            "improvement_suggestion": self.get_field("improvement_suggestion"),
            "would_recommend": self.get_field("would_recommend"),
        }

        client = bigquery.Client()
        errors = client.insert_rows_json(BIGQUERY_TABLE, [row])
        if errors:
            logging.error("BigQuery insert failed: %s", errors)
        else:
            logging.info("Row written to BigQuery: %s", row)

        rating = self.get_field("product_rating")
        self.hangup(
            final_instructions=(
                f"Thank {self.contact_name} warmly for their feedback. "
                + (
                    "Let them know their input means a lot and the product team will take note of their suggestion. "
                    if int(rating or 0) <= 3
                    else "Tell them it's great to hear they're having a good experience. "
                )
                + "Wish them a great day."
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Product feedback survey → BigQuery → Looker Studio")
    parser.add_argument("phone", help="Phone number to call (E.164 format, e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Contact's full name")
    parser.add_argument("--product", required=True, help="Product name")
    args = parser.parse_args()

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=ProductFeedbackController(
            contact_name=args.name,
            product_name=args.product,
        ),
    )
