import logging
import os

import guava
import psycopg2
import psycopg2.extras
from guava import logging_utils


def get_connection():
    return psycopg2.connect(
        host=os.environ["PGHOST"],
        port=int(os.environ.get("PGPORT", "5432")),
        user=os.environ["PGUSER"],
        password=os.environ["PGPASSWORD"],
        dbname=os.environ["PGDATABASE"],
    )


def get_account_by_email(email: str) -> dict | None:
    """Returns the account and contact name for the given email, or None."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT a.id, a.name AS account_name, a.plan,
                       u.full_name AS contact_name
                FROM accounts a
                JOIN users u ON u.account_id = a.id AND u.email = %s
                LIMIT 1
                """,
                (email,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def create_feature_request(
    account_id: int | None,
    contact_name: str,
    contact_email: str,
    category: str,
    title: str,
    description: str,
    business_impact: str,
) -> int:
    """Inserts a feature request and returns the new ID."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO feature_requests
                    (account_id, contact_name, contact_email, category,
                     title, description, business_impact, status, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'submitted', NOW())
                RETURNING id
                """,
                (
                    account_id,
                    contact_name,
                    contact_email,
                    category,
                    title,
                    description,
                    business_impact,
                ),
            )
            return cur.fetchone()[0]


agent = guava.Agent(
    name="Blake",
    organization="Nexus Cloud",
    purpose=(
        "to help Nexus Cloud customers submit feature requests to the product team"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "submit_request",
        objective=(
            "A customer is calling to request a new feature or improvement. "
            "Verify their identity, understand what they need, and log a detailed request "
            "for the product team."
        ),
        checklist=[
            guava.Say(
                "Thanks for calling Nexus Cloud. I'm Blake. "
                "We love hearing from customers about what would make the platform better. "
                "Let me get your feedback logged for the product team."
            ),
            guava.Field(
                key="caller_email",
                field_type="text",
                description="Ask for their email address to verify their account.",
                required=True,
            ),
            guava.Field(
                key="category",
                field_type="multiple_choice",
                description="Ask which area of the product their request relates to.",
                choices=[
                    "API and integrations",
                    "dashboard and reporting",
                    "authentication and security",
                    "billing and subscription",
                    "performance and reliability",
                    "data management",
                    "other",
                ],
                required=True,
            ),
            guava.Field(
                key="title",
                field_type="text",
                description=(
                    "Ask them to give their request a short name — "
                    "what they'd call the feature in one phrase."
                ),
                required=True,
            ),
            guava.Field(
                key="description",
                field_type="text",
                description=(
                    "Ask them to describe the feature in detail — what they'd like it to do "
                    "and how they'd expect it to work."
                ),
                required=True,
            ),
            guava.Field(
                key="business_impact",
                field_type="text",
                description=(
                    "Ask how this feature would help their team — what problem it solves "
                    "or what they'd be able to do that they can't today."
                ),
                required=True,
            ),
        ],
    )


@agent.on_task_complete("submit_request")
def on_done(call: guava.Call) -> None:
    email = (call.get_field("caller_email") or "").strip().lower()
    category = call.get_field("category") or "other"
    title = call.get_field("title") or "Untitled request"
    description = call.get_field("description") or ""
    impact = call.get_field("business_impact") or ""

    logging.info("Feature request from %s: [%s] %s", email, category, title)

    try:
        account = get_account_by_email(email)
    except Exception as e:
        logging.error("DB error looking up %s: %s", email, e)
        account = None

    account_id = account["id"] if account else None
    name = (account or {}).get("contact_name") or "there"

    try:
        request_id = create_feature_request(
            account_id=account_id,
            contact_name=name,
            contact_email=email,
            category=category,
            title=title,
            description=description,
            business_impact=impact,
        )
        logging.info("Feature request #%d created for %s", request_id, name)
        call.hangup(
            final_instructions=(
                f"Thank {name} for taking the time to share their feedback. "
                f"Let them know their feature request has been logged as #{request_id}: '{title}'. "
                "The product team reviews all submissions and they'll receive an email update "
                "if the feature moves forward on the roadmap. "
                "Acknowledge the value of their feedback and thank them for being a Nexus Cloud customer."
            )
        )
    except Exception as e:
        logging.error("Failed to save feature request for %s: %s", email, e)
        call.hangup(
            final_instructions=(
                f"Apologize to {name} for a technical issue. "
                "Ask them to email product@nexuscloud.io with their request and assure them "
                "the team will review it within a few business days."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
