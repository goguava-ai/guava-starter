import argparse
import logging
import os
from datetime import datetime

import guava
import requests
from guava import logging_utils


def _signin() -> tuple[str, str]:
    resp = requests.post(
        f"{os.environ['TABLEAU_SERVER_URL']}/api/3.21/auth/signin",
        json={
            "credentials": {
                "personalAccessTokenName": os.environ["TABLEAU_PAT_NAME"],
                "personalAccessTokenSecret": os.environ["TABLEAU_PAT_SECRET"],
                "site": {"contentUrl": os.environ["TABLEAU_SITE_NAME"]},
            }
        },
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        timeout=15,
    )
    resp.raise_for_status()
    creds = resp.json()["credentials"]
    return creds["token"], creds["site"]["id"]


_TOKEN, _SITE_ID = _signin()
SERVER_URL = os.environ["TABLEAU_SERVER_URL"]
HEADERS = {"X-Tableau-Auth": _TOKEN, "Content-Type": "application/json", "Accept": "application/json"}
API_BASE = f"{SERVER_URL}/api/3.21/sites/{_SITE_ID}"


def get_workbook(workbook_id: str) -> dict:
    """Fetches workbook metadata by ID."""
    resp = requests.get(
        f"{API_BASE}/workbooks/{workbook_id}",
        headers=HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("workbook", {})


agent = guava.Agent(
    name="Alex",
    organization="Vertex Analytics",
    purpose=(
        "to notify users when their Tableau workbook refresh has completed or failed "
        "and capture any follow-up actions they need"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    workbook_id = call.get_variable("workbook_id")
    contact_name = call.get_variable("contact_name")

    # Fetch workbook details before the call
    workbook_name = "your workbook"
    updated_display = "recently"
    size_display = ""

    try:
        workbook = get_workbook(workbook_id)
        workbook_name = workbook.get("name", workbook_name)
        updated_at_str = workbook.get("updatedAt", "")
        if updated_at_str:
            updated_at = datetime.fromisoformat(updated_at_str.replace("Z", "+00:00"))
            updated_display = updated_at.strftime("%B %d, %Y at %I:%M %p UTC")
        size_bytes = workbook.get("size")
        if size_bytes is not None:
            size_mb = int(size_bytes) / (1024 * 1024)
            size_display = f"{size_mb:.1f} MB"
    except Exception as e:
        logging.error("Failed to fetch workbook %s pre-call: %s", workbook_id, e)

    call.set_variable("workbook_name", workbook_name)
    call.set_variable("updated_display", updated_display)
    call.set_variable("size_display", size_display)

    call.reach_person(contact_full_name=contact_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    contact_name = call.get_variable("contact_name")
    workbook_id = call.get_variable("workbook_id")
    refresh_status = call.get_variable("refresh_status")

    workbook_name = call.get_variable("workbook_name")
    updated_display = call.get_variable("updated_display")
    size_display = call.get_variable("size_display") or ""

    if outcome == "unavailable":
        logging.info(
            "Unable to reach %s for workbook refresh notification on workbook %s",
            contact_name, workbook_id,
        )
        status_word = "completed" if refresh_status == "completed" else "encountered an issue"
        call.hangup(
            final_instructions=(
                f"Leave a brief voicemail for {contact_name} on behalf of Vertex Analytics. "
                f"Let them know the refresh for the Tableau workbook '{workbook_name}' has "
                f"{status_word} and ask them to reach out to the analytics team if they have "
                "any questions. Keep it concise and professional."
            )
        )
    elif outcome == "available":
        if refresh_status == "completed":
            status_message = (
                f"I'm calling to let you know that the refresh for your Tableau workbook "
                f"'{workbook_name}' has completed successfully. "
                f"It was last updated on {updated_display}."
            )
            if size_display:
                status_message += f" The workbook is currently {size_display}."
        else:
            status_message = (
                f"I'm calling to let you know that the refresh for your Tableau workbook "
                f"'{workbook_name}' has unfortunately failed. "
                "Our team has been notified, but I wanted to make sure you were aware directly."
            )

        call.set_task(
            "record_outcome",
            objective=(
                f"Notify {contact_name} about the Tableau workbook refresh "
                f"{'completion' if refresh_status == 'completed' else 'failure'} "
                f"for '{workbook_name}'. Capture their reaction and any issues they've noticed."
            ),
            checklist=[
                guava.Say(
                    f"Hi {contact_name}, this is Alex from Vertex Analytics. "
                    + status_message
                ),
                guava.Field(
                    key="satisfaction",
                    field_type="multiple_choice",
                    description=(
                        "Ask the user how they'd characterize the situation — are they satisfied "
                        "with the refresh outcome, do they need someone to review it, or will "
                        "they check the workbook themselves?"
                    ),
                    choices=["satisfied", "needs-review", "will-check-myself"],
                    required=True,
                ),
                guava.Field(
                    key="any_issues",
                    field_type="text",
                    description=(
                        "Ask if they've noticed any data issues or discrepancies in the workbook "
                        "that they'd like the analytics team to look into. "
                        "Skip if they're satisfied and have no concerns."
                    ),
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("record_outcome")
def on_done(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    workbook_id = call.get_variable("workbook_id")
    refresh_status = call.get_variable("refresh_status")
    satisfaction = call.get_field("satisfaction") or "satisfied"
    any_issues = call.get_field("any_issues") or ""

    logging.info(
        "Refresh notification outcome for workbook %s — status: %s, satisfaction: %s",
        workbook_id, refresh_status, satisfaction,
    )
    if any_issues:
        logging.info("Issues reported: %s", any_issues)

    if satisfaction == "needs-review":
        issue_note = f" They noted: {any_issues}." if any_issues else ""
        call.hangup(
            final_instructions=(
                f"Let {contact_name} know the analytics team will review the workbook "
                f"'{call.get_variable('workbook_name')}' and follow up with them shortly.{issue_note} "
                "Thank them for flagging it and wish them a great day."
            )
        )
    elif satisfaction == "will-check-myself":
        call.hangup(
            final_instructions=(
                f"Acknowledge that {contact_name} will check the workbook themselves. "
                "Let them know the analytics team is available if they have any questions "
                "after reviewing. Wish them a great day."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {contact_name} for their time. "
                "Let them know the analytics team is here if anything comes up. "
                "Wish them a great day."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound call to notify a user of a Tableau workbook refresh result."
    )
    parser.add_argument("phone", help="User phone number (E.164, e.g. +15551234567)")
    parser.add_argument("--workbook-id", required=True, help="Tableau workbook ID")
    parser.add_argument("--name", required=True, help="User's full name")
    parser.add_argument(
        "--status",
        required=True,
        choices=["completed", "failed"],
        help="Refresh status to report to the user",
    )
    args = parser.parse_args()

    logging.info(
        "Initiating workbook refresh notification to %s (%s) for workbook %s (status: %s)",
        args.name, args.phone, args.workbook_id, args.status,
    )

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "workbook_id": args.workbook_id,
            "contact_name": args.name,
            "refresh_status": args.status,
        },
    )
