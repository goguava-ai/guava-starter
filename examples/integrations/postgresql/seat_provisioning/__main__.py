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
    """Returns the account, seat counts, and user role for the given email."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT a.id, a.name AS account_name, a.plan,
                       a.seats_total, a.seats_used, a.renewal_date,
                       u.full_name AS contact_name, u.role
                FROM accounts a
                JOIN users u ON u.account_id = a.id AND u.email = %s
                LIMIT 1
                """,
                (email,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def log_seat_request(
    account_id: int, contact_name: str, seats_requested: int, notes: str
) -> int:
    """Logs a seat provisioning request and returns the request ID."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO seat_requests
                    (account_id, contact_name, seats_requested, notes, status, created_at)
                VALUES (%s, %s, %s, %s, 'pending', NOW())
                RETURNING id
                """,
                (account_id, contact_name, seats_requested, notes),
            )
            return cur.fetchone()[0]


agent = guava.Agent(
    name="Sam",
    organization="Nexus Cloud",
    purpose=(
        "to help Nexus Cloud account admins add seats to their subscription"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "process_seat_request",
        objective=(
            "An account admin has called to add seats to their Nexus Cloud subscription. "
            "Verify their identity, check their current seat usage, "
            "and log a provisioning request for the account team."
        ),
        checklist=[
            guava.Say(
                "Thanks for calling Nexus Cloud. I'm Sam. "
                "I can help you add seats to your account. "
                "Let me pull up your details first."
            ),
            guava.Field(
                key="caller_email",
                field_type="text",
                description="Ask for the email address on their account.",
                required=True,
            ),
            guava.Field(
                key="seats_requested",
                field_type="integer",
                description="Ask how many additional seats they'd like to add.",
                required=True,
            ),
            guava.Field(
                key="notes",
                field_type="text",
                description=(
                    "Ask if there's any context the team should know — "
                    "for example, new hires starting, a team expansion, or urgency."
                ),
                required=False,
            ),
        ],
    )


@agent.on_task_complete("process_seat_request")
def on_done(call: guava.Call) -> None:
    email = (call.get_field("caller_email") or "").strip().lower()
    notes = call.get_field("notes") or ""

    try:
        seats_requested = int(call.get_field("seats_requested") or 0)
    except (TypeError, ValueError):
        seats_requested = 0

    logging.info("Seat provisioning request from %s: %d seats", email, seats_requested)

    try:
        account = get_account_by_email(email)
    except Exception as e:
        logging.error("DB error looking up %s: %s", email, e)
        account = None

    if not account:
        call.hangup(
            final_instructions=(
                "Let the caller know you couldn't find an account with that email. "
                "Ask them to verify it or offer to transfer them to a billing specialist."
            )
        )
        return

    name = account.get("contact_name") or "there"
    account_id = account["id"]
    plan = account.get("plan") or "current"
    seats_total = int(account.get("seats_total") or 0)
    seats_used = int(account.get("seats_used") or 0)
    seats_available = max(0, seats_total - seats_used)

    if seats_requested <= 0:
        call.hangup(
            final_instructions=(
                f"Let {name} know you need a valid number of seats to proceed. "
                "Ask them to call back once they know how many seats they need."
            )
        )
        return

    try:
        request_id = log_seat_request(account_id, name, seats_requested, notes)
        logging.info(
            "Seat request #%d: account %d requests %d seats (has %d/%d)",
            request_id, account_id, seats_requested, seats_used, seats_total,
        )
        renewal = account.get("renewal_date")
        renewal_str = renewal.strftime("%B %d, %Y") if renewal else "your next renewal date"

        call.hangup(
            final_instructions=(
                f"Let {name} know their request to add {seats_requested} seat(s) has been logged "
                f"as request #{request_id}. "
                f"Current usage: {seats_used} of {seats_total} seats in use, "
                f"{seats_available} currently available. "
                "An account manager will reach out within one business day to confirm pricing "
                f"and activate the new seats. New seats are prorated to {renewal_str}. "
                "Thank them for growing with Nexus Cloud."
            )
        )
    except Exception as e:
        logging.error("Failed to log seat request for %s: %s", name, e)
        call.hangup(
            final_instructions=(
                f"Apologize to {name} for a technical issue. "
                "Ask them to email billing@nexuscloud.io with the number of seats they need "
                "and someone will follow up within one business day."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
