import guava
import os
import logging
from guava import logging_utils
import argparse
import requests


RETOOL_CHECKLIST_WEBHOOK_URL = os.environ["RETOOL_ONBOARDING_WORKFLOW_URL"]
RETOOL_CHECKLIST_API_KEY = os.environ["RETOOL_ONBOARDING_API_KEY"]

HEADERS = {
    "X-Workflow-Api-Key": RETOOL_CHECKLIST_API_KEY,
    "Content-Type": "application/json",
}


def get_onboarding_status(employee_id: str) -> dict:
    """Fetch the employee's current onboarding checklist from Retool."""
    resp = requests.get(
        RETOOL_CHECKLIST_WEBHOOK_URL,
        headers=HEADERS,
        params={"employee_id": employee_id, "action": "get_status"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def update_onboarding_status(employee_id: str, completed_items: list, notes: str) -> None:
    """Write the verified checklist outcomes back to Retool."""
    resp = requests.post(
        RETOOL_CHECKLIST_WEBHOOK_URL,
        headers=HEADERS,
        json={
            "action": "update_status",
            "employee_id": employee_id,
            "completed_items": completed_items,
            "call_notes": notes,
            "source": "voice",
        },
        timeout=10,
    )
    resp.raise_for_status()


agent = guava.Agent(
    name="Jordan",
    organization="Acme Corp People Ops",
    purpose=(
        "to check in with new Acme Corp employees about their onboarding progress "
        "and make sure they have everything they need"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    employee_name = call.get_variable("employee_name")
    employee_id = call.get_variable("employee_id")
    start_date = call.get_variable("start_date")

    # Fetch their checklist before the call connects.
    pending_items: list = []
    try:
        status = get_onboarding_status(employee_id)
        pending_items = status.get("pending_items") or []
    except Exception as e:
        logging.warning("Could not fetch onboarding status for %s: %s", employee_id, e)
        pending_items = [
            "laptop setup",
            "ID badge pickup",
            "benefits enrollment",
            "security training",
            "first-day manager meeting",
        ]

    call.set_variable("pending_items", pending_items)
    call.reach_person(contact_full_name=employee_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    employee_name = call.get_variable("employee_name")
    start_date = call.get_variable("start_date")

    if outcome == "unavailable":
        logging.info("Unable to reach %s for onboarding check", employee_name)
        call.hangup(
            final_instructions=(
                f"Leave a brief, friendly voicemail for {employee_name} from Acme Corp People Ops. "
                "Let them know you were calling to check in on their onboarding and that they can "
                "call back or reply to the onboarding email with any questions. "
                "Keep it warm and brief."
            )
        )
    elif outcome == "available":
        pending_items = call.get_variable("pending_items") or []
        pending_list = (
            ", ".join(pending_items) if pending_items else "all items"
        )

        call.set_task(
            "record_and_close",
            objective=(
                f"Check in with {employee_name}, a new hire who started on {start_date}. "
                f"Verify completion of their outstanding onboarding items: {pending_list}."
            ),
            checklist=[
                guava.Say(
                    f"Hi {employee_name}! This is Jordan calling from Acme Corp People Ops. "
                    f"I'm doing a quick check-in to see how your first few days are going and "
                    "make sure everything on your onboarding checklist is taken care of. "
                    "Do you have just a couple minutes?"
                ),
                guava.Field(
                    key="overall_experience",
                    field_type="multiple_choice",
                    description=(
                        "Ask how their first days have been going overall."
                    ),
                    choices=["great", "good", "okay", "having some difficulties"],
                    required=True,
                ),
                guava.Field(
                    key="completed_items",
                    field_type="text",
                    description=(
                        f"Walk through their pending onboarding items one by one: {', '.join(pending_items)}. "
                        "Ask which ones they've completed. Note any that are still outstanding."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="blockers",
                    field_type="text",
                    description=(
                        "Ask if there's anything blocking them or any items they need help with. "
                        "Capture any specific issues — missing access, unclear instructions, etc."
                    ),
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("record_and_close")
def on_done(call: guava.Call) -> None:
    employee_name = call.get_variable("employee_name")
    employee_id = call.get_variable("employee_id")

    experience = call.get_field("overall_experience") or "good"
    completed_text = call.get_field("completed_items") or ""
    blockers = call.get_field("blockers") or ""

    logging.info(
        "Onboarding check-in complete for %s (ID: %s) — experience: %s",
        employee_name, employee_id, experience,
    )

    notes = f"Experience: {experience}. Completed: {completed_text}."
    if blockers:
        notes += f" Blockers: {blockers}"

    pending_items = call.get_variable("pending_items") or []
    completed_items = [
        item for item in pending_items
        if item.lower() in completed_text.lower()
    ]

    try:
        update_onboarding_status(employee_id, completed_items, notes)
        logging.info(
            "Updated onboarding status for %s — %d items confirmed complete",
            employee_id, len(completed_items),
        )
    except Exception as e:
        logging.error("Failed to update onboarding status for %s: %s", employee_id, e)

    if experience == "having some difficulties" or blockers:
        call.hangup(
            final_instructions=(
                f"Empathize with {employee_name} and let them know that a People Ops "
                "team member will follow up to help resolve any outstanding items. "
                "Let them know they can always reach us at the IT helpdesk or via email. "
                "Encourage them — starting a new job is a lot, and the team is here to help."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Wrap up warmly with {employee_name}. Let them know their checklist "
                "has been updated and they're in great shape. "
                "Remind them that People Ops is always available if anything comes up. "
                "Welcome them to the team and wish them a great rest of their first week."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound onboarding check-in call for a new employee."
    )
    parser.add_argument("phone", help="Employee phone number (E.164, e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Employee full name")
    parser.add_argument("--employee-id", required=True, help="Employee ID in Retool")
    parser.add_argument("--start-date", required=True, help="Start date (e.g. 'Monday, March 31')")
    args = parser.parse_args()

    logging.info(
        "Initiating onboarding check-in call to %s (%s)", args.name, args.phone
    )

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "employee_name": args.name,
            "employee_id": args.employee_id,
            "start_date": args.start_date,
        },
    )
