import guava
import os
import logging
from guava import logging_utils
import requests
from datetime import datetime, timezone


BASE_ID = os.environ["AIRTABLE_BASE_ID"]
TABLE_NAME = os.environ.get("AIRTABLE_LEADS_TABLE", "Leads")
BASE_URL = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_NAME}"


def get_headers() -> dict:
    return {
        "Authorization": f"Bearer {os.environ['AIRTABLE_API_KEY']}",
        "Content-Type": "application/json",
    }


def create_lead(fields: dict) -> dict | None:
    resp = requests.post(
        BASE_URL,
        headers=get_headers(),
        json={"fields": fields},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


agent = guava.Agent(
    name="Alex",
    organization="Meridian Team",
    purpose=(
        "to capture inbound lead information and log it to the Meridian Team CRM in Airtable"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "save_lead",
        objective=(
            "An inbound lead has called. Collect their contact information, company details, "
            "and what they're looking for, then log it to Airtable."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Meridian Team. This is Alex. "
                "I'd love to learn a bit about you and what you're looking for today."
            ),
            guava.Field(
                key="first_name",
                field_type="text",
                description="Ask for their first name.",
                required=True,
            ),
            guava.Field(
                key="last_name",
                field_type="text",
                description="Ask for their last name.",
                required=True,
            ),
            guava.Field(
                key="company",
                field_type="text",
                description="Ask what company they're with.",
                required=False,
            ),
            guava.Field(
                key="email",
                field_type="text",
                description="Ask for their email address so we can follow up.",
                required=True,
            ),
            guava.Field(
                key="phone",
                field_type="text",
                description="Ask for the best phone number to reach them.",
                required=False,
            ),
            guava.Field(
                key="inquiry",
                field_type="text",
                description=(
                    "Ask what brings them in — what are they looking for help with? "
                    "Capture their main interest or pain point."
                ),
                required=True,
            ),
            guava.Field(
                key="urgency",
                field_type="multiple_choice",
                description="Ask roughly when they're looking to get started.",
                choices=["immediately", "within a month", "within 3 months", "just exploring"],
                required=True,
            ),
        ],
    )


@agent.on_task_complete("save_lead")
def on_done(call: guava.Call) -> None:
    first_name = call.get_field("first_name") or ""
    last_name = call.get_field("last_name") or ""
    company = call.get_field("company") or ""
    email = call.get_field("email") or ""
    phone = call.get_field("phone") or ""
    inquiry = call.get_field("inquiry") or ""
    urgency = call.get_field("urgency") or ""

    fields = {
        "Name": f"{first_name} {last_name}".strip(),
        "Email": email,
        "Company": company,
        "Phone": phone,
        "Inquiry": inquiry,
        "Urgency": urgency,
        "Source": "Inbound Phone Call",
        "Status": "New",
        "Date Captured": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }
    # Remove empty optional fields
    fields = {k: v for k, v in fields.items() if v}

    logging.info("Saving lead to Airtable: %s %s (%s)", first_name, last_name, email)

    created = None
    try:
        created = create_lead(fields)
        logging.info("Lead created in Airtable: %s", created.get("id") if created else None)
    except Exception as e:
        logging.error("Failed to create Airtable record: %s", e)

    if created:
        call.hangup(
            final_instructions=(
                f"Thank {first_name} for reaching out. Let them know a member of the Meridian Team "
                "will follow up at the email they provided within one business day. "
                "Wish them a great day."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {first_name} for reaching out. Let them know we've noted their interest "
                "and someone will be in touch soon. If there were any issues logging the info, "
                "let them know our team will follow up either way. Wish them a great day."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
