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
    """Returns the account and contact details for the given email, or None."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT a.id, a.name AS account_name, a.plan, a.status,
                       u.full_name AS contact_name
                FROM accounts a
                JOIN users u ON u.account_id = a.id AND u.email = %s
                LIMIT 1
                """,
                (email,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def get_recent_invoices(account_id: int, limit: int = 3) -> list[dict]:
    """Returns the most recent invoices for an account."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT invoice_number, amount, currency, status,
                       period_start, period_end, due_date, paid_at
                FROM invoices
                WHERE account_id = %s
                ORDER BY period_start DESC
                LIMIT %s
                """,
                (account_id, limit),
            )
            return [dict(r) for r in cur.fetchall()]


agent = guava.Agent(
    name="Jamie",
    organization="Nexus Cloud",
    purpose=(
        "to help Nexus Cloud customers understand their invoices and billing history"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "handle_billing_inquiry",
        objective=(
            "A customer has called with a billing question. "
            "Verify their identity by email, look up their account and recent invoices, "
            "and address their inquiry."
        ),
        checklist=[
            guava.Say(
                "Thanks for calling Nexus Cloud. I'm Jamie from billing. "
                "I can pull up your invoice details right now. "
                "Let me verify your identity first."
            ),
            guava.Field(
                key="caller_email",
                field_type="text",
                description="Ask for the email address on their account.",
                required=True,
            ),
            guava.Field(
                key="inquiry_type",
                field_type="multiple_choice",
                description="Ask what their billing question is about.",
                choices=[
                    "recent invoice amount",
                    "payment status",
                    "charge I don't recognize",
                    "request a refund",
                    "update payment method",
                    "other billing question",
                ],
                required=True,
            ),
        ],
    )


@agent.on_task_complete("handle_billing_inquiry")
def on_done(call: guava.Call) -> None:
    email = (call.get_field("caller_email") or "").strip().lower()
    inquiry = call.get_field("inquiry_type") or "other billing question"

    logging.info("Billing inquiry from %s: %s", email, inquiry)

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

    account_id = account["id"]
    name = account.get("contact_name") or account.get("account_name") or "there"
    plan = account.get("plan") or "unknown"

    try:
        invoices = get_recent_invoices(account_id)
    except Exception as e:
        logging.error("Failed to fetch invoices for account %d: %s", account_id, e)
        invoices = []

    invoice_lines = []
    for inv in invoices:
        amount = inv.get("amount")
        currency = (inv.get("currency") or "USD").upper()
        status = inv.get("status") or "unknown"
        number = inv.get("invoice_number") or "N/A"
        period_start = inv.get("period_start")
        period_end = inv.get("period_end")
        amount_str = f"${float(amount):,.2f} {currency}" if amount else ""
        period_str = ""
        if period_start and period_end:
            period_str = f"{period_start.strftime('%b %d')}–{period_end.strftime('%b %d, %Y')}"
        line = f"Invoice {number}: {amount_str}, {status}"
        if period_str:
            line += f" ({period_str})"
        invoice_lines.append(line)

    invoice_summary = "; ".join(invoice_lines) if invoice_lines else "no recent invoices found"

    logging.info("Billing inquiry handled for %s, account %d", name, account_id)

    special_note = ""
    if "refund" in inquiry:
        special_note = (
            "They've requested a refund — let them know refund requests are reviewed within "
            "2 business days and they'll receive an email confirmation once processed. "
        )
    elif "update payment" in inquiry:
        special_note = (
            "For updating a payment method, direct them to Settings → Billing in the dashboard, "
            "or offer to have a billing specialist assist them securely. "
        )
    elif "don't recognize" in inquiry:
        special_note = (
            "For an unrecognized charge, walk them through what each invoice covers "
            "and offer to escalate to a billing specialist if they need a detailed breakdown. "
        )

    call.hangup(
        final_instructions=(
            f"Greet {name} by name. "
            f"Their account is on the {plan} plan. "
            f"Recent billing history: {invoice_summary}. "
            f"They called about: {inquiry}. "
            + special_note
            + "Answer their question as fully as you can. "
            "If they need something beyond what you have, offer to escalate to the billing team."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
