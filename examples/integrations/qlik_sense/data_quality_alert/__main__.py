import argparse
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


def get_reload_log(reload_id: str) -> str:
    """Fetch a truncated reload log for context."""
    try:
        resp = requests.get(
            f"{QLIK_TENANT_URL}/api/v1/reloads/{reload_id}/log",
            headers=HEADERS,
            timeout=10,
        )
        resp.raise_for_status()
        log_text = resp.text or ""
        # Return the last 500 characters as a summary of the error.
        return log_text[-500:].strip() if log_text else ""
    except Exception:
        return ""


def cancel_or_stop_reload(reload_id: str) -> None:
    try:
        requests.delete(
            f"{QLIK_TENANT_URL}/api/v1/reloads/{reload_id}",
            headers=HEADERS,
            timeout=10,
        )
    except Exception as e:
        logging.warning("Could not stop reload %s: %s", reload_id, e)


agent = guava.Agent(
    name="Morgan",
    organization="Apex Analytics",
    purpose=(
        "to alert data stewards when a Qlik app reload fails or data quality "
        "issues are detected, and coordinate a response"
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
    alert_type = call.get_variable("alert_type")
    alert_detail = call.get_variable("alert_detail")

    if outcome == "unavailable":
        logging.warning(
            "Unable to reach %s for data quality alert on app '%s'",
            recipient_name, app_name,
        )
        call.hangup(
            final_instructions=(
                f"Leave an urgent but professional voicemail for {recipient_name} from Apex Analytics. "
                f"Let them know there is a {alert_type} on the '{app_name}' Qlik app "
                "and they should check their email immediately for details. "
                "Ask them to call back or reply to the alert email as soon as possible."
            )
        )
    elif outcome == "available":
        call.set_task(
            "handle_response",
            objective=(
                f"Alert {recipient_name} to a data quality issue in the "
                f"'{app_name}' Qlik app and capture their response."
            ),
            checklist=[
                guava.Say(
                    f"Hi {recipient_name}, this is Morgan from Apex Analytics. "
                    f"I'm calling about a data quality alert on the '{app_name}' Qlik app. "
                    f"We detected a {alert_type}: {alert_detail}. "
                    "I wanted to flag this so you can take a look."
                ),
                guava.Field(
                    key="aware",
                    field_type="multiple_choice",
                    description="Ask if they're already aware of this issue.",
                    choices=[
                        "yes, I know about it — already working on it",
                        "yes, I know — it's expected behavior",
                        "no, this is new to me",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="action",
                    field_type="multiple_choice",
                    description="Ask what action they'd like taken on the Qlik side.",
                    choices=[
                        "leave the app as-is — I'll fix the source data and re-trigger",
                        "stop any running reload immediately",
                        "escalate to the data engineering team",
                        "no action needed from the Qlik side",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="additional_context",
                    field_type="text",
                    description=(
                        "Ask if there's any additional context about this issue — "
                        "for example, a known upstream outage or a planned schema change."
                    ),
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("handle_response")
def on_done(call: guava.Call) -> None:
    recipient_name = call.get_variable("recipient_name")
    app_name = call.get_variable("app_name")
    app_id = call.get_variable("app_id")
    reload_id = call.get_variable("reload_id")

    aware = call.get_field("aware") or "no, this is new to me"
    action = call.get_field("action") or "no action needed from the Qlik side"
    context = call.get_field("additional_context") or ""

    logging.info(
        "Data quality alert response from %s for app '%s': aware=%s, action=%s",
        recipient_name, app_name, aware, action,
    )

    if "stop any running reload" in action and reload_id:
        try:
            cancel_or_stop_reload(reload_id)
            logging.info("Stopped reload %s for app %s", reload_id, app_id)
        except Exception as e:
            logging.error("Failed to stop reload %s: %s", reload_id, e)

    if "escalate" in action:
        call.hangup(
            final_instructions=(
                f"Let {recipient_name} know you've noted the escalation request "
                "and the data engineering team will be looped in right away via a Slack alert "
                "and email. "
                + (f"Context noted: {context}." if context else "")
                + " Thank them for the quick response."
            )
        )
    elif "stop" in action:
        call.hangup(
            final_instructions=(
                f"Let {recipient_name} know the reload has been stopped. "
                "Once the source data is corrected, they can trigger a new reload from "
                f"the Qlik Cloud console or by calling back. "
                + (f"Context noted: {context}." if context else "")
                + " Thank them for their time."
            )
        )
    elif "expected behavior" in aware:
        call.hangup(
            final_instructions=(
                f"Thank {recipient_name} for the clarification. "
                "Let them know the alert has been noted and the team will review "
                "whether the threshold needs to be adjusted. Wish them a good day."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {recipient_name} for their response. "
                "Let them know the analytics team will monitor the situation and "
                "follow up by email with next steps. "
                + (f"Context noted: {context}." if context else "")
                + " Wish them a good day."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound alert call when a Qlik app has a data quality issue."
    )
    parser.add_argument("phone", help="Recipient phone number (E.164)")
    parser.add_argument("--name", required=True, help="Recipient full name")
    parser.add_argument("--app-name", required=True, help="Qlik app name")
    parser.add_argument("--app-id", required=True, help="Qlik app ID")
    parser.add_argument("--reload-id", default="", help="Reload job ID (if applicable)")
    parser.add_argument(
        "--alert-type",
        default="reload failure",
        help="Type of alert (e.g. 'reload failure', 'row count anomaly')",
    )
    parser.add_argument(
        "--alert-detail",
        required=True,
        help="Brief description of the issue",
    )
    args = parser.parse_args()

    logging.info(
        "Alerting %s (%s) about %s on app '%s'",
        args.name, args.phone, args.alert_type, args.app_name,
    )

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "recipient_name": args.name,
            "app_name": args.app_name,
            "app_id": args.app_id,
            "reload_id": args.reload_id,
            "alert_type": args.alert_type,
            "alert_detail": args.alert_detail,
        },
    )
