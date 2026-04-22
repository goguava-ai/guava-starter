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
    name="Alex",
    organization="Acme Corp",
    purpose="to collect a brief NPS score from a recent customer",
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    call.reach_person(contact_full_name=contact_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    contact_name = call.get_variable("contact_name")

    if outcome == "unavailable":
        call.hangup()
    elif outcome == "available":
        call.set_task(
            "save_to_bigquery",
            objective=f"Conduct a brief NPS survey with {contact_name}.",
            checklist=[
                guava.Say(
                    f"Hi {contact_name}, this is Alex from Acme Corp. "
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
        )


@agent.on_task_complete("save_to_bigquery")
def on_done(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")

    row = {
        "call_timestamp": datetime.now(timezone.utc).isoformat(),
        "contact_name": contact_name,
        "nps_score": call.get_field("nps_score"),
        "reason": call.get_field("reason"),
    }

    client = bigquery.Client()
    errors = client.insert_rows_json(BIGQUERY_TABLE, [row])
    if errors:
        logging.error("BigQuery insert failed: %s", errors)
    else:
        logging.info("Row written to BigQuery: %s", row)

    call.hangup(
        final_instructions="Thank them warmly for their feedback and wish them a great day."
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(description="NPS survey → BigQuery → Looker Studio")
    parser.add_argument("phone", help="Phone number to call (E.164 format, e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Contact's full name")
    args = parser.parse_args()

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={"contact_name": args.name},
    )
