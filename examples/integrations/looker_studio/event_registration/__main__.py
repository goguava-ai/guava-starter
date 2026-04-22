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


agent = guava.Agent(
    name="Sam",
    organization="Acme Corp",
    purpose=f"to register callers for {EVENT_NAME}",
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    date_note = f" on {EVENT_DATE}" if EVENT_DATE else ""

    call.set_task(
        "save_to_bigquery",
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
    )


@agent.on_task_complete("save_to_bigquery")
def on_done(call: guava.Call) -> None:
    row = {
        "call_timestamp": datetime.now(timezone.utc).isoformat(),
        "full_name": call.get_field("full_name"),
        "email": call.get_field("email"),
        "company": call.get_field("company"),
        "ticket_count": call.get_field("ticket_count"),
        "session_preference": call.get_field("session_preference"),
        "dietary_requirements": call.get_field("dietary_requirements"),
        "event_name": EVENT_NAME,
    }

    client = bigquery.Client()
    errors = client.insert_rows_json(BIGQUERY_TABLE, [row])
    if errors:
        logging.error("BigQuery insert failed: %s", errors)
    else:
        logging.info("Row written to BigQuery: %s", row)

    name = call.get_field("full_name") or "there"
    tickets = call.get_field("ticket_count") or 1
    session = call.get_field("session_preference") or "their preferred session"

    call.hangup(
        final_instructions=(
            f"Let {name} know they're registered for {EVENT_NAME}. "
            f"Confirm {tickets} ticket(s) and their session preference: {session}. "
            "Let them know a confirmation email with details will arrive shortly. "
            "Thank them and let them know we look forward to seeing them there."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
