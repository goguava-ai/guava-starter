import guava
import os
import logging
from guava import logging_utils
import argparse
import requests


TENANT_ID = os.environ["POWERBI_TENANT_ID"]
CLIENT_ID = os.environ["POWERBI_CLIENT_ID"]
CLIENT_SECRET = os.environ["POWERBI_CLIENT_SECRET"]
WORKSPACE_ID = os.environ["POWERBI_WORKSPACE_ID"]
DATASET_ID = os.environ["POWERBI_KPI_DATASET_ID"]

# Name of the table in the push dataset that holds KPI rows.
KPI_TABLE = os.environ.get("POWERBI_KPI_TABLE", "DailyMetrics")

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


def get_latest_kpi_rows(token: str, top: int = 1) -> list[dict]:
    """
    Fetch the most recent rows from a Power BI push dataset table.
    Push datasets expose their rows via the REST API.
    """
    resp = requests.get(
        f"{BASE_URL}/groups/{WORKSPACE_ID}/datasets/{DATASET_ID}/tables/{KPI_TABLE}/rows",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    resp.raise_for_status()
    rows = resp.json().get("value", [])
    return rows[-top:] if rows else []


def format_kpi_row(row: dict) -> str:
    """Format a KPI row as a readable spoken summary."""
    parts = []
    for key, value in row.items():
        if key.startswith("_"):
            continue
        label = key.replace("_", " ").title()
        if isinstance(value, float):
            parts.append(f"{label}: {value:,.2f}")
        elif isinstance(value, int):
            parts.append(f"{label}: {value:,}")
        else:
            parts.append(f"{label}: {value}")
    return ". ".join(parts)


agent = guava.Agent(
    name="Quinn",
    organization="Apex Analytics",
    purpose=(
        "to deliver the daily KPI briefing to Apex Analytics team members "
        "by reading key metrics from Power BI"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    recipient_name = call.get_variable("recipient_name")

    call.kpi_summary = ""
    try:
        token = get_access_token()
        rows = get_latest_kpi_rows(token)
        if rows:
            call.kpi_summary = format_kpi_row(rows[0])
    except Exception as e:
        logging.error("Failed to fetch KPI data from Power BI: %s", e)

    call.reach_person(contact_full_name=recipient_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    recipient_name = call.get_variable("recipient_name")

    if outcome == "unavailable":
        logging.info("Unable to reach %s for daily KPI briefing", recipient_name)
        call.hangup(
            final_instructions=(
                f"Leave a brief voicemail for {recipient_name} from Apex Analytics. "
                "Let them know you called with their daily KPI briefing and that the metrics "
                "are available in their Power BI dashboard. Keep it under 15 seconds."
            )
        )
    elif outcome == "available":
        if not call.kpi_summary:
            call.set_task(
                "deliver_briefing",
                objective=f"Inform {recipient_name} that today's KPI data is unavailable.",
                checklist=[
                    guava.Say(
                        f"Hi {recipient_name}, this is Quinn from Apex Analytics. "
                        "I'm calling with your daily briefing, but unfortunately I wasn't able "
                        "to retrieve today's metrics from Power BI. Our team will look into it. "
                        "Have a great day."
                    ),
                ],
            )
        else:
            call.set_task(
                "deliver_briefing",
                objective=f"Deliver today's KPI briefing to {recipient_name}.",
                checklist=[
                    guava.Say(
                        f"Good morning {recipient_name}! This is Quinn from Apex Analytics "
                        "with your daily KPI briefing from Power BI. "
                        f"Here are today's numbers: {call.kpi_summary}."
                    ),
                    guava.Field(
                        key="questions",
                        field_type="text",
                        description=(
                            "Ask if they have any questions about today's numbers or "
                            "if they'd like to flag anything for the analytics team."
                        ),
                        required=False,
                    ),
                ],
            )


@agent.on_task_complete("deliver_briefing")
def on_done(call: guava.Call) -> None:
    recipient_name = call.get_variable("recipient_name")
    questions = call.get_field("questions") or ""

    if questions:
        logging.info(
            "KPI briefing questions from %s: %s", recipient_name, questions
        )

    call.hangup(
        final_instructions=(
            f"Wrap up the briefing with {recipient_name}. "
            + (
                f"Acknowledge their question or feedback — '{questions}' — "
                "and let them know the analytics team will follow up by email. "
                if questions
                else ""
            )
            + "Wish them a productive day."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(description="Outbound daily KPI briefing call.")
    parser.add_argument("phone", help="Recipient phone number (E.164)")
    parser.add_argument("--name", required=True, help="Recipient full name")
    args = parser.parse_args()

    logging.info("Initiating daily KPI briefing call to %s (%s)", args.name, args.phone)

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={"recipient_name": args.name},
    )
