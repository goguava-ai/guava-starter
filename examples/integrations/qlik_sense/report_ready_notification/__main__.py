import guava
import os
import logging
from guava import logging_utils
import argparse
import requests


QLIK_TENANT_URL = os.environ["QLIK_TENANT_URL"].rstrip("/")
QLIK_API_KEY = os.environ["QLIK_API_KEY"]

HEADERS = {
    "Authorization": f"Bearer {QLIK_API_KEY}",
    "Content-Type": "application/json",
}


def get_reload_details(reload_id: str) -> dict | None:
    resp = requests.get(
        f"{QLIK_TENANT_URL}/api/v1/reloads/{reload_id}",
        headers=HEADERS,
        timeout=10,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def get_app_details(app_id: str) -> dict | None:
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
    name="Casey",
    organization="Apex Analytics",
    purpose=(
        "to notify Apex Analytics stakeholders when their Qlik reports have "
        "finished reloading and are ready to view"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    recipient_name = call.get_variable("recipient_name")
    call.reach_person(contact_full_name=recipient_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    recipient_name = call.get_variable("recipient_name")
    app_name = call.get_variable("app_name")
    app_id = call.get_variable("app_id")
    reload_duration_minutes = call.get_variable("reload_duration_minutes")

    if outcome == "unavailable":
        logging.info(
            "Unable to reach %s for report-ready notification on app %s",
            recipient_name, app_name,
        )
        call.hangup(
            final_instructions=(
                f"Leave a brief, upbeat voicemail for {recipient_name} from Apex Analytics. "
                f"Let them know the '{app_name}' Qlik report has finished reloading "
                "and is ready to view. Keep it under 15 seconds."
            )
        )
    elif outcome == "available":
        app_url = f"{QLIK_TENANT_URL}/sense/app/{app_id}"
        duration_note = (
            f" The reload completed in {reload_duration_minutes} minutes."
            if reload_duration_minutes
            else ""
        )

        call.set_task(
            "close_notification",
            objective=(
                f"Notify {recipient_name} that the '{app_name}' Qlik app has "
                "finished reloading and is ready for review."
            ),
            checklist=[
                guava.Say(
                    f"Hi {recipient_name}! This is Casey from Apex Analytics. "
                    f"I'm calling to let you know that your Qlik report, '{app_name}', "
                    f"has finished reloading and is ready to view.{duration_note} "
                    "The data is fresh as of right now."
                ),
                guava.Field(
                    key="feedback",
                    field_type="multiple_choice",
                    description=(
                        "Ask if they have any questions about the reload or if there's "
                        "anything specific they'd like the analytics team to check."
                    ),
                    choices=[
                        "no, I'll check it now",
                        "yes, I have a question for the team",
                        "please send me the link by email",
                    ],
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("close_notification")
def on_done(call: guava.Call) -> None:
    recipient_name = call.get_variable("recipient_name")
    app_name = call.get_variable("app_name")
    app_id = call.get_variable("app_id")

    app_url = f"{QLIK_TENANT_URL}/sense/app/{app_id}"
    feedback = call.get_field("feedback") or "no, I'll check it now"

    logging.info(
        "Report-ready notification delivered to %s for app '%s': %s",
        recipient_name, app_name, feedback,
    )

    if "question" in feedback:
        call.hangup(
            final_instructions=(
                f"Let {recipient_name} know the analytics team will follow up "
                "by email to address their question. Thank them for flagging it. "
                "Remind them the report is live and ready at their convenience."
            )
        )
    elif "email" in feedback:
        call.hangup(
            final_instructions=(
                f"Let {recipient_name} know you'll have the analytics team send them "
                f"a direct link to the report by email. The app is '{app_name}'. "
                "Thank them and wish them a good day."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Wish {recipient_name} a great review session. "
                f"Let them know the link is available at {app_url} if they need it. "
                "Thank them for their time."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound notification call when a Qlik app reload completes."
    )
    parser.add_argument("phone", help="Recipient phone number (E.164)")
    parser.add_argument("--name", required=True, help="Recipient full name")
    parser.add_argument("--app-name", required=True, help="Qlik app name")
    parser.add_argument("--app-id", required=True, help="Qlik app ID")
    parser.add_argument("--reload-id", default="", help="Reload job ID")
    parser.add_argument("--duration", default="", help="Reload duration in minutes")
    args = parser.parse_args()

    logging.info("Notifying %s (%s) — Qlik app '%s' is ready", args.name, args.phone, args.app_name)

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "recipient_name": args.name,
            "app_name": args.app_name,
            "app_id": args.app_id,
            "reload_id": args.reload_id,
            "reload_duration_minutes": args.duration,
        },
    )
