import argparse
import logging
import os
from datetime import datetime, timezone

import guava
from google.cloud import bigquery
from guava import logging_utils

# Set this to your BigQuery table: "your_project.your_dataset.your_table"
BIGQUERY_TABLE = os.environ["BIGQUERY_TABLE"]


agent = guava.Agent(
    name="Morgan",
    organization="Acme Corp",
    purpose=(
        "to understand why a customer recently cancelled "
        "and whether there's anything Acme Corp can do to improve"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    call.reach_person(contact_full_name=contact_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    contact_name = call.get_variable("contact_name")
    account_name = call.get_variable("account_name")

    if outcome == "unavailable":
        call.hangup()
    elif outcome == "available":
        call.set_task(
            "save_to_bigquery",
            objective=(
                f"Conduct a brief exit survey with {contact_name} from {account_name}. "
                "The goal is to understand why they cancelled and whether they'd ever return."
            ),
            checklist=[
                guava.Say(
                    f"Hi {contact_name}, this is Morgan from Acme Corp. "
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
        )


@agent.on_task_complete("save_to_bigquery")
def on_done(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    account_name = call.get_variable("account_name")

    row = {
        "call_timestamp": datetime.now(timezone.utc).isoformat(),
        "contact_name": contact_name,
        "account_name": account_name,
        "primary_reason": call.get_field("primary_reason"),
        "competitor_chosen": call.get_field("competitor_chosen"),
        "would_return": call.get_field("would_return"),
        "feedback": call.get_field("feedback"),
    }

    client = bigquery.Client()
    errors = client.insert_rows_json(BIGQUERY_TABLE, [row])
    if errors:
        logging.error("BigQuery insert failed: %s", errors)
    else:
        logging.info("Row written to BigQuery: %s", row)

    call.hangup(
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

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "contact_name": args.name,
            "account_name": args.account,
        },
    )
