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
    name="Riley",
    organization="Acme Corp",
    purpose=(
        "to reach out to a prospect, introduce Acme Corp, "
        "and understand their interest level"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    call.reach_person(contact_full_name=contact_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    contact_name = call.get_variable("contact_name")
    company_name = call.get_variable("company_name")

    if outcome == "unavailable":
        row = {
            "call_timestamp": datetime.now(timezone.utc).isoformat(),
            "contact_name": contact_name,
            "company_name": company_name,
            "interest_level": None,
            "next_step": "voicemail",
            "budget_confirmed": None,
            "reached": False,
            "notes": None,
        }

        client = bigquery.Client()
        errors = client.insert_rows_json(BIGQUERY_TABLE, [row])
        if errors:
            logging.error("BigQuery insert failed: %s", errors)

        call.hangup(
            final_instructions=(
                f"Leave a brief voicemail for {contact_name}. "
                "Introduce yourself as Riley from Acme Corp, mention you're reaching out about "
                "how we help teams with [value prop], and leave a callback number. Keep it under 20 seconds."
            )
        )
    elif outcome == "available":
        call.set_task(
            "save_to_bigquery",
            objective=(
                f"Have a brief introductory sales conversation with {contact_name} "
                f"at {company_name}. Understand their interest level and agree on a next step."
            ),
            checklist=[
                guava.Say(
                    f"Hi {contact_name}, this is Riley calling from Acme Corp. "
                    "I'm reaching out because we help companies like yours with [value prop]. "
                    "I was wondering if I could take just two minutes to share what we do "
                    "and see if it might be a fit."
                ),
                guava.Field(
                    key="interest_level",
                    field_type="multiple_choice",
                    description="Based on the conversation, capture their level of interest.",
                    choices=[
                        "very interested",
                        "somewhat interested",
                        "not interested right now",
                        "asked to call back later",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="next_step",
                    field_type="multiple_choice",
                    description="Agree on and capture the next step.",
                    choices=[
                        "demo scheduled",
                        "follow-up email to send",
                        "call back in 1–2 weeks",
                        "no next step",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="budget_confirmed",
                    field_type="multiple_choice",
                    description="Ask if budget is available for a solution like this.",
                    choices=["yes", "no", "unknown"],
                    required=True,
                ),
                guava.Field(
                    key="notes",
                    field_type="text",
                    description=(
                        "Capture any relevant notes from the conversation — "
                        "pain points, timing, objections, or context for the sales team."
                    ),
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("save_to_bigquery")
def on_done(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    company_name = call.get_variable("company_name")

    row = {
        "call_timestamp": datetime.now(timezone.utc).isoformat(),
        "contact_name": contact_name,
        "company_name": company_name,
        "interest_level": call.get_field("interest_level"),
        "next_step": call.get_field("next_step"),
        "budget_confirmed": call.get_field("budget_confirmed"),
        "reached": True,
        "notes": call.get_field("notes"),
    }

    client = bigquery.Client()
    errors = client.insert_rows_json(BIGQUERY_TABLE, [row])
    if errors:
        logging.error("BigQuery insert failed: %s", errors)
    else:
        logging.info("Row written to BigQuery: %s", row)

    next_step = call.get_field("next_step") or ""
    call.hangup(
        final_instructions=(
            f"Wrap up the call with {contact_name} warmly. "
            + (
                "Confirm the demo details and let them know they'll receive a calendar invite shortly. "
                if "demo" in next_step
                else "Let them know you'll follow up by email shortly. "
                if "email" in next_step
                else "Thank them for their time and let them know you'll be in touch. "
            )
            + "Wish them a great day."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(description="Sales call outcome → BigQuery → Looker Studio")
    parser.add_argument("phone", help="Phone number to call (E.164 format, e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Contact's full name")
    parser.add_argument("--company", required=True, help="Company name")
    args = parser.parse_args()

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "contact_name": args.name,
            "company_name": args.company,
        },
    )
