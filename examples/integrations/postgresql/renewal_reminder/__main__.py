import guava
import os
import logging
from guava import logging_utils
import argparse
import psycopg2
import psycopg2.extras
from datetime import date



def get_connection():
    return psycopg2.connect(
        host=os.environ["PGHOST"],
        port=int(os.environ.get("PGPORT", "5432")),
        user=os.environ["PGUSER"],
        password=os.environ["PGPASSWORD"],
        dbname=os.environ["PGDATABASE"],
    )


def get_account(account_id: int) -> dict | None:
    """Returns account details including plan and renewal date."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT name, plan, status, renewal_date, seats_total, seats_used
                FROM accounts
                WHERE id = %s
                """,
                (account_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def log_renewal_outcome(account_id: int, outcome: str, intent: str) -> None:
    """Records the renewal call outcome in account_events."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO account_events
                    (account_id, event_type, details, created_at)
                VALUES (%s, 'renewal_reminder_call', %s, NOW())
                """,
                (account_id, f"outcome={outcome}; renew_intent={intent}"),
            )


agent = guava.Agent(
    name="Jordan",
    organization="Nexus Cloud",
    purpose=(
        "to remind Nexus Cloud customers about upcoming subscription renewals "
        "and confirm their plans"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    account_id = int(call.get_variable("account_id"))

    call.contact_name = contact_name
    call.account_id = account_id
    call.account_name = ""
    call.plan = "current"
    call.renewal_str = ""
    call.days_until_renewal = None

    try:
        account = get_account(account_id)
        if account:
            call.account_name = account.get("name") or ""
            call.plan = account.get("plan") or "current"
            renewal = account.get("renewal_date")
            if renewal:
                call.days_until_renewal = (renewal - date.today()).days
                call.renewal_str = renewal.strftime("%B %d, %Y")
    except Exception as e:
        logging.error("Failed to fetch account %d: %s", account_id, e)

    call.reach_person(contact_full_name=contact_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    if outcome == "unavailable":
        logging.info(
            "Unable to reach %s for renewal reminder on account %d",
            call.contact_name, call.account_id,
        )
        try:
            log_renewal_outcome(call.account_id, "voicemail", "unknown")
        except Exception as e:
            logging.error("Failed to log outcome: %s", e)
        call.hangup(
            final_instructions=(
                f"Leave a brief voicemail for {call.contact_name} from Nexus Cloud. "
                f"Mention that their subscription renews on {call.renewal_str} and "
                "ask them to call back or log in to make any changes. Keep it brief."
            )
        )
    elif outcome == "available":
        days_note = (
            f" in {call.days_until_renewal} days" if call.days_until_renewal is not None else ""
        )

        call.set_task(
            "handle_response",
            objective=(
                f"Remind {call.contact_name} at {call.account_name or 'their company'} that their "
                f"Nexus Cloud {call.plan} plan renews{days_note} on {call.renewal_str}. "
                "Confirm they want to renew and check if they'd like to make any changes."
            ),
            checklist=[
                guava.Say(
                    f"Hi {call.contact_name}, this is Jordan from Nexus Cloud. "
                    f"I'm calling to give you a heads-up that your {call.plan} subscription "
                    f"is coming up for renewal{days_note} on {call.renewal_str}. "
                    "I wanted to make sure everything looks good on your end."
                ),
                guava.Field(
                    key="renewal_intent",
                    field_type="multiple_choice",
                    description="Ask if they plan to renew their subscription.",
                    choices=[
                        "yes, renew as-is",
                        "yes, but I'd like to change my plan",
                        "no, I'd like to cancel",
                        "not sure yet",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="any_concerns",
                    field_type="text",
                    description=(
                        "Ask if there's anything they'd like to discuss before renewal — "
                        "pricing, features, or changes to their team size."
                    ),
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("handle_response")
def on_done(call: guava.Call) -> None:
    intent = call.get_field("renewal_intent") or "not sure"
    concerns = call.get_field("any_concerns") or ""

    logging.info(
        "Renewal reminder handled for account %d — intent: %s", call.account_id, intent
    )

    if "as-is" in intent:
        outcome = "confirmed"
    elif "change" in intent:
        outcome = "change_requested"
    elif "cancel" in intent:
        outcome = "cancel_requested"
    else:
        outcome = "undecided"

    try:
        log_renewal_outcome(call.account_id, outcome, intent)
    except Exception as e:
        logging.error("Failed to log renewal outcome for account %d: %s", call.account_id, e)

    if "as-is" in intent:
        call.hangup(
            final_instructions=(
                f"Thank {call.contact_name} for confirming their renewal. "
                f"Let them know their {call.plan} plan will automatically renew on {call.renewal_str} "
                "and they'll receive an invoice by email. "
                "Wish them continued success and thank them for being a Nexus Cloud customer."
            )
        )
    elif "change" in intent:
        call.hangup(
            final_instructions=(
                f"Thank {call.contact_name} for letting you know. "
                "Let them know an account manager will reach out by end of day to walk through "
                "plan options and ensure a smooth transition before the renewal date. "
                + (f"Note their concern: {concerns}. " if concerns else "")
                + "Thank them for their time."
            )
        )
    elif "cancel" in intent:
        call.hangup(
            final_instructions=(
                f"Acknowledge {call.contact_name}'s request to cancel. "
                "Let them know a retention specialist will reach out within one business day "
                "to walk through the cancellation process and explore any alternatives. "
                "Assure them no changes will be made until they've spoken with someone. "
                "Thank them for being a customer."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {call.contact_name} for their time. "
                f"Remind them their renewal date is {call.renewal_str} and they can make changes "
                "anytime through the Nexus Cloud dashboard or by calling back. "
                "Wish them a great day."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound renewal reminder call for a Nexus Cloud account."
    )
    parser.add_argument("phone", help="Contact's phone number (E.164, e.g. +15551234567)")
    parser.add_argument("--account-id", required=True, type=int, help="Account ID in the database")
    parser.add_argument("--name", required=True, help="Contact's full name")
    args = parser.parse_args()

    logging.info(
        "Initiating renewal reminder call to %s (%s) for account %d",
        args.name, args.phone, args.account_id,
    )

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "contact_name": args.name,
            "account_id": str(args.account_id),
        },
    )
