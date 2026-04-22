import logging
import os

import guava
import psycopg2
import psycopg2.extras
from guava import logging_utils

PRIORITY_MAP = {
    "blocking my entire team": "critical",
    "blocking me personally": "high",
    "degraded but still working": "medium",
    "minor inconvenience": "low",
}


def get_connection():
    return psycopg2.connect(
        host=os.environ["PGHOST"],
        port=int(os.environ.get("PGPORT", "5432")),
        user=os.environ["PGUSER"],
        password=os.environ["PGPASSWORD"],
        dbname=os.environ["PGDATABASE"],
    )


def create_incident(
    title: str,
    description: str,
    priority: str,
    reporter_name: str,
    reporter_email: str,
    affected_service: str,
) -> int:
    """Inserts an incident row and returns the new incident ID."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO incidents
                    (title, description, priority, status,
                     reporter_name, reporter_email, affected_service, created_at)
                VALUES (%s, %s, %s, 'open', %s, %s, %s, NOW())
                RETURNING id
                """,
                (title, description, priority, reporter_name, reporter_email, affected_service),
            )
            return cur.fetchone()[0]


agent = guava.Agent(
    name="Morgan",
    organization="Nexus Cloud",
    purpose=(
        "to help Nexus Cloud customers report technical incidents and open "
        "a tracked record for the engineering team"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "file_incident",
        objective=(
            "A customer is calling to report a technical issue with Nexus Cloud. "
            "Collect their contact details, a clear description of the problem, "
            "the affected service, and impact level, then create an incident record."
        ),
        checklist=[
            guava.Say(
                "Thanks for calling Nexus Cloud support. I'm Morgan. "
                "I'm sorry to hear you're experiencing an issue — let me get this "
                "documented right away so the right team can look into it."
            ),
            guava.Field(
                key="reporter_name",
                field_type="text",
                description="Ask for their full name.",
                required=True,
            ),
            guava.Field(
                key="reporter_email",
                field_type="text",
                description="Ask for their email address so we can send updates.",
                required=True,
            ),
            guava.Field(
                key="affected_service",
                field_type="multiple_choice",
                description="Ask which Nexus Cloud service is affected.",
                choices=[
                    "API gateway",
                    "authentication",
                    "data pipeline",
                    "dashboard",
                    "webhooks",
                    "billing",
                    "other",
                ],
                required=True,
            ),
            guava.Field(
                key="description",
                field_type="text",
                description=(
                    "Ask them to describe the issue in their own words — what's happening, "
                    "when it started, and any error messages they've seen."
                ),
                required=True,
            ),
            guava.Field(
                key="impact",
                field_type="multiple_choice",
                description="Ask how severely this is impacting their work right now.",
                choices=list(PRIORITY_MAP.keys()),
                required=True,
            ),
        ],
    )


@agent.on_task_complete("file_incident")
def on_done(call: guava.Call) -> None:
    name = call.get_field("reporter_name") or "Unknown"
    email = call.get_field("reporter_email") or ""
    service = call.get_field("affected_service") or "unknown"
    description = call.get_field("description") or "No description provided"
    impact = call.get_field("impact") or "minor inconvenience"

    priority = PRIORITY_MAP.get(impact, "medium")
    title = f"{service.title()} issue — {name}"

    logging.info(
        "Filing incident for %s: service=%s, priority=%s", name, service, priority
    )

    try:
        incident_id = create_incident(
            title=title,
            description=description,
            priority=priority,
            reporter_name=name,
            reporter_email=email,
            affected_service=service,
        )
        logging.info("Incident #%d created", incident_id)

        urgency_note = (
            "This has been flagged as critical and our on-call engineer is being paged immediately. "
            if priority == "critical"
            else "Our engineering team will review it shortly. "
        )

        call.hangup(
            final_instructions=(
                f"Let {name} know their incident has been logged as #{incident_id} "
                f"with {priority} priority. "
                + urgency_note
                + "They'll receive email updates as the team investigates. "
                "Apologize for the disruption and thank them for reporting it promptly."
            )
        )
    except Exception as e:
        logging.error("Failed to create incident for %s: %s", name, e)
        call.hangup(
            final_instructions=(
                f"Apologize to {name} for a technical issue logging the incident. "
                "Ask them to email support@nexuscloud.io with the details, and assure them "
                "someone will respond within 30 minutes for urgent issues."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
