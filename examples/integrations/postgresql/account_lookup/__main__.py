import guava
import os
import logging
from guava import logging_utils
import psycopg2
import psycopg2.extras



def get_connection():
    return psycopg2.connect(
        host=os.environ["PGHOST"],
        port=int(os.environ.get("PGPORT", "5432")),
        user=os.environ["PGUSER"],
        password=os.environ["PGPASSWORD"],
        dbname=os.environ["PGDATABASE"],
    )


def get_account_by_email(email: str) -> dict | None:
    """Returns the account associated with the given email, or None."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT a.id, a.name, a.plan, a.status,
                       a.seats_total, a.seats_used,
                       a.api_calls_this_month, a.api_call_limit,
                       a.created_at, a.renewal_date,
                       u.email, u.full_name AS contact_name, u.role
                FROM accounts a
                JOIN users u ON u.account_id = a.id AND u.email = %s
                LIMIT 1
                """,
                (email,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


agent = guava.Agent(
    name="Alex",
    organization="Nexus Cloud",
    purpose=(
        "to help Nexus Cloud customers look up their account details, "
        "plan information, and usage statistics"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "look_up_account",
        objective=(
            "A customer has called to check on their Nexus Cloud account. "
            "Verify their identity with their email address, look up their account, "
            "and answer questions about their plan, seat usage, and API usage."
        ),
        checklist=[
            guava.Say(
                "Thanks for calling Nexus Cloud. I'm Alex. "
                "I can pull up your account details. Let me verify your identity first."
            ),
            guava.Field(
                key="caller_email",
                field_type="text",
                description="Ask for their email address on file.",
                required=True,
            ),
        ],
    )


@agent.on_task_complete("look_up_account")
def on_done(call: guava.Call) -> None:
    email = (call.get_field("caller_email") or "").strip().lower()
    logging.info("Looking up Nexus Cloud account for email: %s", email)

    try:
        account = get_account_by_email(email)
    except Exception as e:
        logging.error("Database error for email %s: %s", email, e)
        account = None

    if not account:
        call.hangup(
            final_instructions=(
                "Let the caller know you couldn't find an account associated with that email. "
                "Ask them to verify it or offer to transfer them to a billing specialist."
            )
        )
        return

    name = account.get("contact_name") or account.get("name") or "there"
    plan = account.get("plan") or "unknown"
    status = account.get("status") or "active"
    seats_total = account.get("seats_total") or 0
    seats_used = account.get("seats_used") or 0
    seats_available = max(0, int(seats_total) - int(seats_used))
    api_calls = account.get("api_calls_this_month") or 0
    api_limit = account.get("api_call_limit") or 0
    renewal = account.get("renewal_date")
    renewal_str = renewal.strftime("%B %d, %Y") if renewal else "unknown"

    usage_pct = round((int(api_calls) / int(api_limit)) * 100) if api_limit else 0

    logging.info(
        "Account found for %s: plan=%s, status=%s, seats=%d/%d, api=%d/%d",
        name, plan, status, seats_used, seats_total, api_calls, api_limit,
    )

    call.hangup(
        final_instructions=(
            f"Greet {name} by name. "
            f"Their account details: plan is {plan}, status is {status}. "
            f"Seats: {seats_used} of {seats_total} in use, {seats_available} available. "
            f"API usage this month: {int(api_calls):,} of {int(api_limit):,} calls "
            f"({usage_pct}% used). "
            f"Renewal date: {renewal_str}. "
            "Answer any questions they have about their account. "
            "If they want to add seats or upgrade, offer to connect them with their account manager."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
