import argparse
import logging
import os

import guava
import requests
from guava import logging_utils

TENANT_ID = os.environ["POWERBI_TENANT_ID"]
CLIENT_ID = os.environ["POWERBI_CLIENT_ID"]
CLIENT_SECRET = os.environ["POWERBI_CLIENT_SECRET"]
WORKSPACE_ID = os.environ["POWERBI_WORKSPACE_ID"]

BASE_URL = "https://api.powerbi.com/v1.0/myorg"


def get_access_token() -> str:
    resp = requests.post(
        f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token",
        data={
            "grant_type": "client_credentials",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "scope": "https://analysis.windows.net/powerbi/api/.default",
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def log_alert_acknowledgment(dataset_id: str, metric_name: str, action: str, token: str) -> None:
    """Push an acknowledgment row back to a Power BI push dataset for audit logging."""
    from datetime import datetime, timezone

    table = os.environ.get("POWERBI_ALERT_LOG_TABLE", "AlertLog")
    payload = {
        "rows": [
            {
                "metric_name": metric_name,
                "action": action,
                "acknowledged_at": datetime.now(timezone.utc).isoformat(),
                "channel": "voice",
            }
        ]
    }
    try:
        resp = requests.post(
            f"{BASE_URL}/groups/{WORKSPACE_ID}/datasets/{dataset_id}/tables/{table}/rows",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload,
            timeout=10,
        )
        resp.raise_for_status()
    except Exception as e:
        logging.warning("Could not log alert acknowledgment to Power BI: %s", e)


agent = guava.Agent(
    name="Alex",
    organization="Apex Analytics",
    purpose=(
        "to notify stakeholders when a monitored Power BI metric breaches a threshold "
        "and capture their response"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    recipient_name = call.get_variable("recipient_name")
    metric_name = call.get_variable("metric_name")
    current_value = call.get_variable("current_value")
    threshold_value = call.get_variable("threshold_value")
    breach_direction = call.get_variable("breach_direction")
    dataset_id = call.get_variable("dataset_id")
    report_url = call.get_variable("report_url")

    token = ""
    try:
        token = get_access_token()
    except Exception as e:
        logging.warning("Could not obtain Power BI token before call: %s", e)

    call.set_variable("token", token)
    call.reach_person(contact_full_name=recipient_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    recipient_name = call.get_variable("recipient_name")
    metric_name = call.get_variable("metric_name")
    current_value = call.get_variable("current_value")
    threshold_value = call.get_variable("threshold_value")
    breach_direction = call.get_variable("breach_direction")

    if outcome == "unavailable":
        logging.warning(
            "Unable to reach %s for alert on metric '%s'",
            recipient_name, metric_name,
        )
        call.hangup(
            final_instructions=(
                f"Leave a brief, urgent-but-calm voicemail for {recipient_name} from Apex Analytics. "
                f"Let them know that '{metric_name}' has breached its threshold "
                f"(currently {current_value} vs threshold of {threshold_value}) "
                "and that they should check their Power BI dashboard. Ask them to call back or reply by email."
            )
        )
    elif outcome == "available":
        call.set_task(
            "deliver_alert",
            objective=(
                f"Notify {recipient_name} that {metric_name} has breached its "
                f"threshold and capture their intended response."
            ),
            checklist=[
                guava.Say(
                    f"Hi {recipient_name}, this is Alex from Apex Analytics. "
                    f"I'm calling with an alert from your Power BI dashboard. "
                    f"Your metric '{metric_name}' is currently at {current_value}, "
                    f"which is {breach_direction} the configured threshold of {threshold_value}. "
                    "I wanted to make sure you're aware and see how you'd like to respond."
                ),
                guava.Field(
                    key="acknowledged",
                    field_type="multiple_choice",
                    description="Ask if they're aware of this and how they'd like to proceed.",
                    choices=[
                        "acknowledged — I'm already on it",
                        "acknowledged — please escalate to the team",
                        "acknowledged — no action needed",
                        "not aware — need more information",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="root_cause",
                    field_type="text",
                    description=(
                        "If they know why the metric breached, ask them to briefly describe "
                        "the root cause or any context they can share."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="eta_to_resolve",
                    field_type="text",
                    description=(
                        "If they're taking action, ask if they have an estimated time to resolve. "
                        "Skip if they said no action is needed."
                    ),
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("deliver_alert")
def on_done(call: guava.Call) -> None:
    recipient_name = call.get_variable("recipient_name")
    metric_name = call.get_variable("metric_name")
    dataset_id = call.get_variable("dataset_id")
    report_url = call.get_variable("report_url")

    ack = call.get_field("acknowledged") or "acknowledged — I'm already on it"
    root_cause = call.get_field("root_cause") or ""
    eta = call.get_field("eta_to_resolve") or ""

    logging.info(
        "Alert acknowledgment for metric '%s': %s (eta: %s)",
        metric_name, ack, eta,
    )

    token = call.get_variable("token") or ""
    if token and dataset_id:
        log_alert_acknowledgment(dataset_id, metric_name, ack, token)

    escalate = "escalate" in ack
    needs_info = "more information" in ack

    if needs_info:
        call.hangup(
            final_instructions=(
                f"Let {recipient_name} know that the full details are visible in "
                f"the Power BI report and that the analytics team will follow up by email "
                "with additional context. Let them know they can also check the dashboard "
                f"directly. Provide the report URL if asked: {report_url}."
            )
        )
    elif escalate:
        call.hangup(
            final_instructions=(
                f"Thank {recipient_name} for their quick response. Let them know "
                "you've noted the escalation and the analytics team will be looped in right away. "
                + (f"Root cause noted: {root_cause}." if root_cause else "")
                + " They'll receive a follow-up by email."
            )
        )
    else:
        eta_note = f" ETA to resolve: {eta}." if eta else ""
        call.hangup(
            final_instructions=(
                f"Thank {recipient_name} for acknowledging the alert.{eta_note} "
                "Let them know the acknowledgment has been logged in Power BI. "
                "Wish them luck resolving it and offer to send a follow-up if needed."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound alert call when a Power BI metric breaches a threshold."
    )
    parser.add_argument("phone", help="Recipient phone number (E.164)")
    parser.add_argument("--name", required=True, help="Recipient full name")
    parser.add_argument("--metric", required=True, help="Name of the metric that breached")
    parser.add_argument("--current-value", required=True, help="Current metric value (as string)")
    parser.add_argument("--threshold", required=True, help="Threshold value that was breached")
    parser.add_argument(
        "--direction",
        default="above",
        choices=["above", "below"],
        help="Whether the value is above or below the threshold",
    )
    parser.add_argument("--dataset-id", default="", help="Power BI dataset ID for logging")
    parser.add_argument("--report-url", default="", help="Power BI report URL to reference")
    args = parser.parse_args()

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "recipient_name": args.name,
            "metric_name": args.metric,
            "current_value": args.current_value,
            "threshold_value": args.threshold,
            "breach_direction": args.direction,
            "dataset_id": args.dataset_id,
            "report_url": args.report_url,
        },
    )
