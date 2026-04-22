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
    name="Jordan",
    organization="Acme Corp",
    purpose="to collect a quick satisfaction rating after a recent support interaction",
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
            objective=f"Collect a brief CSAT survey from {contact_name} about their recent support experience.",
            checklist=[
                guava.Say(
                    f"Hi {contact_name}, this is Jordan from Acme Corp. "
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
        )


@agent.on_task_complete("save_to_bigquery")
def on_done(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    ticket_id = call.get_variable("ticket_id")

    row = {
        "call_timestamp": datetime.now(timezone.utc).isoformat(),
        "contact_name": contact_name,
        "ticket_id": ticket_id,
        "satisfaction_score": call.get_field("satisfaction_score"),
        "was_issue_resolved": call.get_field("was_issue_resolved"),
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

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "contact_name": args.name,
            "ticket_id": args.ticket_id,
        },
    )
