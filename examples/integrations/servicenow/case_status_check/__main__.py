import guava
import os
import logging
from guava import logging_utils
import requests


SN_INSTANCE = os.environ["SERVICENOW_INSTANCE"]
SN_USERNAME = os.environ["SERVICENOW_USERNAME"]
SN_PASSWORD = os.environ["SERVICENOW_PASSWORD"]

BASE_URL = f"https://{SN_INSTANCE}.service-now.com/api/now"
AUTH = (SN_USERNAME, SN_PASSWORD)
HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}

STATE_LABELS = {
    "1": "New",
    "2": "In Progress",
    "3": "On Hold",
    "4": "Resolved",
    "5": "Closed",
    "6": "Cancelled",
}

PRIORITY_LABELS = {
    "1": "Critical",
    "2": "High",
    "3": "Medium",
    "4": "Low",
}


def find_case(case_number: str) -> dict | None:
    """Fetches a CSM case by its number. Returns the record or None."""
    resp = requests.get(
        f"{BASE_URL}/table/sn_customerservice_case",
        auth=AUTH,
        headers=HEADERS,
        params={
            "number": case_number.upper(),
            "sysparm_fields": "number,short_description,state,priority,sys_created_on,sys_updated_on,assigned_to",
            "sysparm_limit": 1,
        },
        timeout=10,
    )
    resp.raise_for_status()
    records = resp.json().get("result", [])
    return records[0] if records else None


agent = guava.Agent(
    name="Sam",
    organization="Vertex Corp",
    purpose=(
        "to help Vertex Corp customers quickly check the status of their "
        "open support cases"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "fetch_status",
        objective=(
            "A customer is calling to check on the status of an existing support case. "
            "Verify their identity, look up the case, and give them a clear status update."
        ),
        checklist=[
            guava.Say(
                "Thanks for calling Vertex Corp Support. I'm Sam. "
                "I can look up the status of your support case — do you have your case number handy?"
            ),
            guava.Field(
                key="case_number",
                field_type="text",
                description=(
                    "Ask for their case number. It typically starts with 'CS' followed by digits "
                    "(e.g. CS0001234). If they don't have it, ask for their email address instead."
                ),
                required=True,
            ),
            guava.Field(
                key="caller_name",
                field_type="text",
                description="Ask for their name to verify it matches the case.",
                required=True,
            ),
        ],
    )


@agent.on_task_complete("fetch_status")
def on_done(call: guava.Call) -> None:
    case_number = (call.get_field("case_number") or "").strip()
    caller_name = call.get_field("caller_name") or "there"

    logging.info("Looking up ServiceNow case: %s for %s", case_number, caller_name)
    try:
        case = find_case(case_number)
    except Exception as e:
        logging.error("ServiceNow case lookup failed: %s", e)
        case = None

    if not case:
        call.hangup(
            final_instructions=(
                f"Let {caller_name} know you couldn't find a case with the number "
                f"'{case_number}'. Ask them to double-check the number or offer to transfer "
                "them to a support agent who can search by email. Be apologetic and helpful."
            )
        )
        return

    state_code = case.get("state", "")
    priority_code = case.get("priority", "")
    subject = case.get("short_description") or "your issue"
    updated = case.get("sys_updated_on", "")[:10] if case.get("sys_updated_on") else "unknown"
    assigned_to_raw = case.get("assigned_to")
    assigned_to = (
        assigned_to_raw.get("display_value", "our team")
        if isinstance(assigned_to_raw, dict)
        else "our team"
    )

    state_label = STATE_LABELS.get(state_code, state_code or "Unknown")
    priority_label = PRIORITY_LABELS.get(priority_code, priority_code or "Unknown")

    logging.info(
        "Case %s — state: %s, priority: %s, last updated: %s",
        case_number, state_label, priority_label, updated,
    )

    call.hangup(
        final_instructions=(
            f"Give {caller_name} a clear status update on their case. "
            f"Case number: {case_number}. "
            f"Issue: {subject}. "
            f"Current status: {state_label}. "
            f"Priority: {priority_label}. "
            f"Last updated: {updated}. "
            f"Assigned to: {assigned_to}. "
            "If the case is On Hold, mention that this usually means we're waiting on a "
            "response or a vendor. If it's Resolved, inform them of that outcome. "
            "Thank them for calling Vertex Corp."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
