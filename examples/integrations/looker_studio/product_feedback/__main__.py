import guava
import os
import logging
from guava import logging_utils
import argparse
from datetime import datetime, timezone

from google.cloud import bigquery


# Set this to your BigQuery table: "your_project.your_dataset.your_table"
BIGQUERY_TABLE = os.environ["BIGQUERY_TABLE"]


agent = guava.Agent(
    name="Taylor",
    organization="Acme Corp",
    purpose=(
        "to collect honest feedback from a customer about their experience with a product"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    call.reach_person(contact_full_name=contact_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    contact_name = call.get_variable("contact_name")
    product_name = call.get_variable("product_name")

    if outcome == "unavailable":
        call.hangup()
    elif outcome == "available":
        call.set_task(
            "save_to_bigquery",
            objective=(
                f"Collect product feedback from {contact_name} "
                f"about their experience with {product_name}."
            ),
            checklist=[
                guava.Say(
                    f"Hi {contact_name}, this is Taylor from Acme Corp. "
                    f"I'm reaching out to hear how you're finding {product_name}. "
                    "It'll take under two minutes — your feedback goes directly to our product team."
                ),
                guava.Field(
                    key="product_rating",
                    field_type="integer",
                    description=(
                        f"Ask them to rate {product_name} overall on a scale of 1 to 5, "
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
        )


@agent.on_task_complete("save_to_bigquery")
def on_done(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    product_name = call.get_variable("product_name")

    row = {
        "call_timestamp": datetime.now(timezone.utc).isoformat(),
        "contact_name": contact_name,
        "product_name": product_name,
        "product_rating": call.get_field("product_rating"),
        "usage_frequency": call.get_field("usage_frequency"),
        "top_feature": call.get_field("top_feature"),
        "improvement_suggestion": call.get_field("improvement_suggestion"),
        "would_recommend": call.get_field("would_recommend"),
    }

    client = bigquery.Client()
    errors = client.insert_rows_json(BIGQUERY_TABLE, [row])
    if errors:
        logging.error("BigQuery insert failed: %s", errors)
    else:
        logging.info("Row written to BigQuery: %s", row)

    rating = call.get_field("product_rating")
    call.hangup(
        final_instructions=(
            f"Thank {contact_name} warmly for their feedback. "
            + (
                "Let them know their input means a lot and the product team will take note of their suggestion. "
                if int(rating or 0) <= 3
                else "Tell them it's great to hear they're having a good experience. "
            )
            + "Wish them a great day."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(description="Product feedback survey → BigQuery → Looker Studio")
    parser.add_argument("phone", help="Phone number to call (E.164 format, e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Contact's full name")
    parser.add_argument("--product", required=True, help="Product name")
    args = parser.parse_args()

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "contact_name": args.name,
            "product_name": args.product,
        },
    )
