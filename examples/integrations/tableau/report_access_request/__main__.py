import logging
import os

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


def find_workbook_by_name(workbook_name: str) -> dict | None:
    """Searches for a workbook by name. Returns the first match or None."""
    resp = requests.get(
        f"{API_BASE}/workbooks",
        headers=HEADERS,
        params={"filter": f"name:eq:{workbook_name}"},
        timeout=10,
    )
    resp.raise_for_status()
    workbooks = resp.json().get("workbooks", {}).get("workbook", [])
    return workbooks[0] if workbooks else None


def tag_workbook_access_requested(workbook_id: str) -> None:
    """Adds an 'access-requested' tag to the workbook to flag it for admin review."""
    resp = requests.put(
        f"{API_BASE}/workbooks/{workbook_id}/tags",
        headers=HEADERS,
        json={"tags": {"tag": [{"label": "access-requested"}]}},
        timeout=10,
    )
    resp.raise_for_status()


agent = guava.Agent(
    name="Morgan",
    organization="Vertex Analytics",
    purpose=(
        "to help callers request access to Tableau workbooks and reports "
        "and route those requests to the appropriate administrator"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "submit_access_request",
        objective=(
            "A caller wants to request access to a specific Tableau workbook or report. "
            "Collect their name, email, the workbook name, and their reason for needing access. "
            "Then tag the workbook in Tableau so an administrator knows to follow up."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Vertex Analytics. This is Morgan. "
                "I can help you request access to a Tableau report or workbook. "
                "I'll just need a few quick details from you."
            ),
            guava.Field(
                key="caller_name",
                field_type="text",
                description="Ask for the caller's full name.",
                required=True,
            ),
            guava.Field(
                key="caller_email",
                field_type="text",
                description="Ask for their work email address so the admin can follow up.",
                required=True,
            ),
            guava.Field(
                key="workbook_name",
                field_type="text",
                description="Ask for the name of the Tableau workbook or report they need access to.",
                required=True,
            ),
            guava.Field(
                key="access_reason",
                field_type="text",
                description=(
                    "Ask why they need access to this report — for example, a project they're "
                    "working on or a decision they need to support. This is optional."
                ),
                required=False,
            ),
        ],
    )


@agent.on_task_complete("submit_access_request")
def on_done(call: guava.Call) -> None:
    caller_name = call.get_field("caller_name") or "Unknown"
    caller_email = call.get_field("caller_email") or ""
    workbook_name = call.get_field("workbook_name") or ""
    access_reason = call.get_field("access_reason") or ""

    logging.info(
        "Access request from %s (%s) for workbook: %s",
        caller_name, caller_email, workbook_name,
    )

    try:
        workbook = find_workbook_by_name(workbook_name)
    except Exception as e:
        logging.error("Workbook lookup failed: %s", e)
        workbook = None

    if not workbook:
        call.hangup(
            final_instructions=(
                f"Let {caller_name} know you couldn't find a workbook named '{workbook_name}'. "
                "Assure them their request has still been noted and a Tableau administrator "
                "will reach out to their email to clarify and grant access. "
                "Thank them for calling Vertex Analytics."
            )
        )
        return

    workbook_id = workbook.get("id", "")
    workbook_display_name = workbook.get("name", workbook_name)

    try:
        tag_workbook_access_requested(workbook_id)
        logging.info(
            "Tagged workbook '%s' (%s) with 'access-requested' for %s",
            workbook_display_name, workbook_id, caller_email,
        )
        if access_reason:
            logging.info("Access reason provided: %s", access_reason)

        call.hangup(
            final_instructions=(
                f"Confirm to {caller_name} that their access request for '{workbook_display_name}' "
                "has been submitted successfully. Let them know a Tableau administrator will "
                f"review the request and follow up at {caller_email} within one business day. "
                "Thank them for calling Vertex Analytics and wish them a great day."
            )
        )
    except Exception as e:
        logging.error("Failed to tag workbook %s: %s", workbook_id, e)
        call.hangup(
            final_instructions=(
                f"Apologize to {caller_name} for a brief technical issue. Let them know "
                "their request for '{workbook_display_name}' has been noted and a "
                "Tableau administrator will follow up at "
                f"{caller_email} to grant access manually. Thank them for their patience."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
