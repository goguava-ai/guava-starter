import logging
import os

import guava
import requests
from guava import logging_utils

QLIK_TENANT_URL = os.environ["QLIK_TENANT_URL"].rstrip("/")
QLIK_API_KEY = os.environ["QLIK_API_KEY"]

HEADERS = {
    "Authorization": f"Bearer {QLIK_API_KEY}",
    "Content-Type": "application/json",
}


def list_apps(space_id: str = "") -> list[dict]:
    """Return the list of apps available to the service account, optionally filtered by space."""
    params: dict = {"limit": 50}
    if space_id:
        params["spaceId"] = space_id
    resp = requests.get(
        f"{QLIK_TENANT_URL}/api/v1/apps",
        headers=HEADERS,
        params=params,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("data", [])


def trigger_reload(app_id: str) -> dict:
    """Trigger a reload for the specified Qlik app and return the reload job."""
    payload = {
        "appId": app_id,
        "partial": False,
    }
    resp = requests.post(
        f"{QLIK_TENANT_URL}/api/v1/reloads",
        headers=HEADERS,
        json=payload,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def get_app(app_id: str) -> dict | None:
    resp = requests.get(
        f"{QLIK_TENANT_URL}/api/v1/apps/{app_id}",
        headers=HEADERS,
        timeout=10,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


agent = guava.Agent(
    name="Riley",
    organization="Apex Analytics",
    purpose=(
        "to help Apex Analytics team members trigger on-demand Qlik app reloads"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    # Pre-load the app list so the agent can confirm the name during the call.
    apps: list = []
    try:
        apps = list_apps()
    except Exception as e:
        logging.warning("Could not pre-load Qlik app list: %s", e)
    call.set_variable("apps", apps)

    call.set_task(
        "trigger_and_respond",
        objective=(
            "An employee has called to request a Qlik app reload. Collect the app ID "
            "or name, confirm it's the right one, and trigger the reload."
        ),
        checklist=[
            guava.Say(
                "Thanks for calling Apex Analytics. This is Riley. "
                "I can trigger a Qlik app reload for you. "
                "What's the name or ID of the app you'd like to reload?"
            ),
            guava.Field(
                key="app_identifier",
                field_type="text",
                description=(
                    "Ask for the Qlik app name or app ID they want to reload. "
                    "If they're unsure of the exact name, ask them to describe it."
                ),
                required=True,
            ),
            guava.Field(
                key="reason",
                field_type="text",
                description=(
                    "Ask briefly why they need the reload now — for example, "
                    "source data was just updated, or they're preparing a report."
                ),
                required=False,
            ),
            guava.Field(
                key="confirmed",
                field_type="multiple_choice",
                description=(
                    "Confirm with them that they want to trigger this reload now. "
                    "A reload will refresh all data in the app."
                ),
                choices=["yes, trigger it now", "no, cancel"],
                required=True,
            ),
        ],
    )


@agent.on_task_complete("trigger_and_respond")
def on_done(call: guava.Call) -> None:
    identifier = (call.get_field("app_identifier") or "").strip()
    reason = call.get_field("reason") or ""
    confirmed = call.get_field("confirmed") or "yes, trigger it now"

    if confirmed != "yes, trigger it now":
        call.hangup(
            final_instructions=(
                "Let the caller know the reload has been cancelled. "
                "Let them know they can call back anytime to trigger it. "
                "Thank them for calling."
            )
        )
        return

    # Try to find the app by ID first, then by name match.
    app_id = ""
    app_name = identifier

    apps = call.get_variable("apps") or []
    matching = [
        a for a in apps
        if identifier.lower() in (a.get("attributes", {}).get("name") or "").lower()
        or identifier == a.get("resourceId") or identifier == a.get("id")
    ]
    if matching:
        best = matching[0]
        app_id = best.get("resourceId") or best.get("id") or ""
        app_name = best.get("attributes", {}).get("name") or identifier
    else:
        # Treat the identifier as a direct app ID
        app_id = identifier

    logging.info(
        "Triggering Qlik reload for app '%s' (ID: %s) — reason: %s",
        app_name, app_id, reason,
    )

    try:
        reload_job = trigger_reload(app_id)
        reload_id = reload_job.get("id") or ""
        logging.info("Qlik reload triggered: reload_id=%s for app=%s", reload_id, app_id)

        call.hangup(
            final_instructions=(
                f"Let the caller know the reload for '{app_name}' has been triggered successfully. "
                f"The reload ID is {reload_id}. Depending on the app size, it may take a few "
                "minutes to complete. They'll be able to see the updated data in Qlik once "
                "the reload finishes. Thank them for calling Apex Analytics."
            )
        )
    except Exception as e:
        logging.error("Failed to trigger Qlik reload for app %s: %s", app_id, e)
        call.hangup(
            final_instructions=(
                f"Apologize — the reload trigger for '{app_name}' failed due to a technical issue. "
                "Let them know our team will investigate and can trigger it manually. "
                "Thank them for their patience."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
