import argparse
import logging
import os
from datetime import datetime, timezone

import guava
import requests
from guava import logging_utils

SN_INSTANCE = os.environ["SERVICENOW_INSTANCE"]
SN_USERNAME = os.environ["SERVICENOW_USERNAME"]
SN_PASSWORD = os.environ["SERVICENOW_PASSWORD"]

BASE_URL = f"https://{SN_INSTANCE}.service-now.com/api/now"
AUTH = (SN_USERNAME, SN_PASSWORD)
HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}


def get_change_request(change_id: str) -> dict | None:
    """Fetches a Change Request by sys_id or number."""
    resp = requests.get(
        f"{BASE_URL}/table/change_request",
        auth=AUTH,
        headers=HEADERS,
        params={
            "number": change_id.upper(),
            "sysparm_fields": "number,short_description,start_date,end_date,risk,state,category",
            "sysparm_limit": 1,
        },
        timeout=10,
    )
    resp.raise_for_status()
    records = resp.json().get("result", [])
    return records[0] if records else None


def add_work_note(change_id: str, note: str) -> None:
    """Adds a work note to the Change Request."""
    resp = requests.patch(
        f"{BASE_URL}/table/change_request/{change_id}",
        auth=AUTH,
        headers=HEADERS,
        json={"work_notes": note},
        timeout=10,
    )
    resp.raise_for_status()


agent = guava.Agent(
    name="Alex",
    organization="Vertex Corp IT",
    purpose=(
        "to notify customers and stakeholders about upcoming planned maintenance windows "
        "and changes that may affect their services"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    change_number = call.get_variable("change_number")

    change_sys_id = ""
    try:
        cr = get_change_request(change_number)
        if cr:
            change_sys_id = cr.get("sys_id", "")
    except Exception as e:
        logging.error("Failed to fetch change request %s pre-call: %s", change_number, e)

    call.set_variable("change_sys_id", change_sys_id)
    call.reach_person(contact_full_name=contact_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    contact_name = call.get_variable("contact_name")
    change_number = call.get_variable("change_number")
    window = call.get_variable("window")

    if outcome == "unavailable":
        logging.info("Unable to reach %s for change notification %s.", contact_name, change_number)

        change_sys_id = call.get_variable("change_sys_id", "")
        if change_sys_id:
            try:
                add_work_note(
                    change_sys_id,
                    f"Change notification attempted — {contact_name} unavailable, voicemail left. "
                    f"Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
                )
            except Exception as e:
                logging.error("Failed to add voicemail work note: %s", e)

        call.hangup(
            final_instructions=(
                f"Leave a professional voicemail for {contact_name} from Vertex Corp IT. "
                f"Let them know you're calling about a scheduled maintenance window "
                f"({change_number}) that may affect their services. "
                f"Mention the window: {window}. Ask them to call back or watch for an "
                "email with full details. Keep it concise."
            )
        )
    elif outcome == "available":
        change_summary = call.get_variable("change_summary")
        call.set_task(
            "log_outcome",
            objective=(
                f"Notify {contact_name} about a planned change window ({change_number}) "
                "that may affect their services. Confirm they received the information."
            ),
            checklist=[
                guava.Say(
                    f"Hi {contact_name}, this is Alex from Vertex Corp IT. "
                    "I'm calling to give you advance notice of a scheduled maintenance window "
                    "that may affect your services."
                ),
                guava.Say(
                    f"Change reference: {change_number}. "
                    f"Summary: {change_summary}. "
                    f"Scheduled window: {window}. "
                    "During this time you may experience brief service interruptions."
                ),
                guava.Field(
                    key="acknowledged",
                    field_type="multiple_choice",
                    description="Ask if they received and understood the notification.",
                    choices=["yes, understood", "has questions or concerns"],
                    required=True,
                ),
                guava.Field(
                    key="concerns",
                    field_type="text",
                    description=(
                        "If they have concerns, ask them to describe the potential impact on their "
                        "work or business. Capture the full detail."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="needs_reschedule",
                    field_type="multiple_choice",
                    description=(
                        "Ask if the scheduled window works for them or if they need to discuss "
                        "an alternative time."
                    ),
                    choices=["window is fine", "need to discuss alternative"],
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("log_outcome")
def on_done(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    change_number = call.get_variable("change_number")

    acknowledged = call.get_field("acknowledged") or "yes, understood"
    concerns = call.get_field("concerns") or ""
    reschedule = call.get_field("needs_reschedule") or "window is fine"

    note_lines = [
        f"Change notification call — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"Notified: {contact_name}",
        f"Acknowledged: {acknowledged}",
        f"Window preference: {reschedule}",
    ]
    if concerns:
        note_lines.append(f"Concerns raised: {concerns}")

    logging.info(
        "Change notification delivered to %s — acknowledged: %s, reschedule: %s",
        contact_name, acknowledged, reschedule,
    )

    change_sys_id = call.get_variable("change_sys_id", "")
    if change_sys_id:
        try:
            add_work_note(change_sys_id, "\n".join(note_lines))
            logging.info("Work note added to change request %s.", change_number)
        except Exception as e:
            logging.error("Failed to add work note to change %s: %s", change_number, e)

    if reschedule == "need to discuss alternative":
        call.hangup(
            final_instructions=(
                f"Let {contact_name} know their request to discuss an alternative window "
                "has been noted. Let them know the change manager will contact them within "
                "one business day to discuss options. Thank them for their time."
            )
        )
    elif acknowledged == "has questions or concerns":
        call.hangup(
            final_instructions=(
                f"Thank {contact_name} for raising their concerns. Let them know "
                "the IT team has been notified and will follow up before the change window. "
                "Wish them a good day."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {contact_name} for their time and for confirming the notification. "
                "Let them know Vertex Corp IT will send an email summary as well. "
                "Wish them a good day."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound change notification call for a ServiceNow Change Request."
    )
    parser.add_argument("phone", help="Contact's phone number (E.164, e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Full name of the contact to notify")
    parser.add_argument("--change-number", required=True, help="ServiceNow Change Request number (e.g. CHG0012345)")
    parser.add_argument("--summary", required=True, help="Brief plain-language summary of the change")
    parser.add_argument("--window", required=True, help="Maintenance window (e.g. 'Saturday March 30, 10 PM – 2 AM ET')")
    args = parser.parse_args()

    logging.info(
        "Initiating change notification call to %s (%s) for %s",
        args.name, args.phone, args.change_number,
    )

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "contact_name": args.name,
            "change_number": args.change_number,
            "change_summary": args.summary,
            "window": args.window,
        },
    )
