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


def get_view(view_id: str) -> dict:
    """Fetches view metadata by ID."""
    resp = requests.get(
        f"{API_BASE}/views/{view_id}",
        headers=HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("view", {})


agent = guava.Agent(
    name="Taylor",
    organization="Vertex Analytics",
    purpose=(
        "to deliver a verbal KPI briefing from a Tableau view and gauge "
        "whether the stakeholder wants to schedule a deeper review"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    view_id = call.get_variable("view_id")
    contact_name = call.get_variable("contact_name")

    # Fetch view metadata before delivering the briefing
    view_name = "the requested view"
    view_owner = "your Tableau team"
    updated_display = "recently"
    content_url = ""

    try:
        view = get_view(view_id)
        view_name = view.get("name", view_name)
        view_owner = view.get("owner", {}).get("name", view_owner)
        content_url = view.get("contentUrl", "")
        updated_at_str = view.get("updatedAt", "")
        if updated_at_str:
            updated_at = datetime.fromisoformat(updated_at_str.replace("Z", "+00:00"))
            updated_display = updated_at.strftime("%B %d, %Y at %I:%M %p UTC")
    except Exception as e:
        logging.error("Failed to fetch view %s pre-call: %s", view_id, e)

    call.set_variable("view_name", view_name)
    call.set_variable("view_owner", view_owner)
    call.set_variable("updated_display", updated_display)
    call.set_variable("content_url", content_url)

    call.reach_person(contact_full_name=contact_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    contact_name = call.get_variable("contact_name")
    view_id = call.get_variable("view_id")

    view_name = call.get_variable("view_name")
    view_owner = call.get_variable("view_owner")
    updated_display = call.get_variable("updated_display")

    if outcome == "unavailable":
        logging.info(
            "Unable to reach %s for insight briefing on view %s",
            contact_name, view_id,
        )
        call.hangup(
            final_instructions=(
                f"Leave a brief, friendly voicemail for {contact_name} on behalf of "
                "Vertex Analytics. Let them know you were calling to share a data briefing on "
                f"the '{view_name}' Tableau view and ask them to call back or reach out "
                "to the analytics team if they'd like a walkthrough. Keep it concise."
            )
        )
    elif outcome == "available":
        owner_note = f" It's maintained by {view_owner}." if view_owner else ""

        call.set_task(
            "save_results",
            objective=(
                f"Deliver a verbal summary of the Tableau view '{view_name}' to "
                f"{contact_name}. Share the view name, when it was last updated, and who "
                f"owns it. Then ask if they'd like to schedule a deeper review session."
            ),
            checklist=[
                guava.Say(
                    f"Hi {contact_name}, this is Taylor calling from Vertex Analytics. "
                    f"I'm reaching out with a quick data briefing on the '{view_name}' "
                    f"Tableau view. It was last updated on {updated_display}.{owner_note} "
                    "I have a summary of the latest KPI metadata I'd like to walk you through."
                ),
                guava.Field(
                    key="wants_review",
                    field_type="multiple_choice",
                    description=(
                        "After sharing the briefing, ask whether the stakeholder would like to "
                        "schedule a deeper review session with the analytics team to go through "
                        "the underlying data in detail."
                    ),
                    choices=["yes", "no"],
                    required=True,
                ),
                guava.Field(
                    key="preferred_time",
                    field_type="text",
                    description=(
                        "If they said yes, ask when would be a good time for them — "
                        "day of week, morning or afternoon, any preferences. Skip if they said no."
                    ),
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("save_results")
def on_done(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    wants_review = call.get_field("wants_review") or "no"
    preferred_time = call.get_field("preferred_time") or ""

    logging.info(
        "Briefing complete for %s — view: %s, wants_review: %s, preferred_time: %s",
        contact_name, call.get_variable("view_name"), wants_review, preferred_time,
    )

    if wants_review == "yes":
        time_note = f" They mentioned {preferred_time} works well." if preferred_time else ""
        call.hangup(
            final_instructions=(
                f"Thank {contact_name} for their time and confirm that you'll have "
                "someone from the analytics team reach out to schedule a deeper review.{time_note} "
                "Wish them a great day."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {contact_name} for their time. Let them know the analytics team "
                "is always available if they have questions about the data in the future. "
                "Wish them a great day."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound Tableau view insight briefing call."
    )
    parser.add_argument("phone", help="Stakeholder phone number (E.164, e.g. +15551234567)")
    parser.add_argument("--view-id", required=True, help="Tableau view ID to brief on")
    parser.add_argument("--name", required=True, help="Stakeholder's full name")
    args = parser.parse_args()

    logging.info(
        "Initiating insight briefing call to %s (%s) for view %s",
        args.name, args.phone, args.view_id,
    )

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "view_id": args.view_id,
            "contact_name": args.name,
        },
    )
