import guava
import os
import logging
from guava import logging_utils
import argparse
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


def get_account_usage(account_id: int) -> dict | None:
    """Returns current usage stats for an account."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT name, plan, api_calls_this_month, api_call_limit,
                       seats_used, seats_total, renewal_date
                FROM accounts
                WHERE id = %s
                """,
                (account_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def log_usage_alert_outcome(account_id: int, outcome: str, intent: str) -> None:
    """Records the call outcome in an account_events table for audit purposes."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO account_events
                    (account_id, event_type, details, created_at)
                VALUES (%s, 'usage_alert_call', %s, NOW())
                """,
                (account_id, f"outcome={outcome}; upgrade_intent={intent}"),
            )


agent = guava.Agent(
    name="Casey",
    organization="Nexus Cloud",
    purpose=(
        "to proactively alert Nexus Cloud customers when their account is approaching "
        "its monthly API usage limit"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    account_id = int(call.get_variable("account_id"))

    account_name = ""
    usage_pct = 0
    calls_used = 0
    calls_limit = 0
    plan = "current"
    renewal_str = ""

    try:
        usage = get_account_usage(account_id)
        if usage:
            account_name = usage.get("name") or ""
            plan = usage.get("plan") or "current"
            calls_used = int(usage.get("api_calls_this_month") or 0)
            calls_limit = int(usage.get("api_call_limit") or 1)
            usage_pct = round((calls_used / calls_limit) * 100)
            renewal = usage.get("renewal_date")
            if renewal:
                renewal_str = renewal.strftime("%B %d")
    except Exception as e:
        logging.error("Failed to fetch usage for account %d: %s", account_id, e)

    call.set_variable("account_name", account_name)
    call.set_variable("usage_pct", usage_pct)
    call.set_variable("calls_used", calls_used)
    call.set_variable("calls_limit", calls_limit)
    call.set_variable("plan", plan)
    call.set_variable("renewal_str", renewal_str)
    call.reach_person(contact_full_name=contact_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    contact_name = call.get_variable("contact_name")
    account_id = int(call.get_variable("account_id"))
    account_name = call.get_variable("account_name") or ""
    usage_pct = call.get_variable("usage_pct") or 0
    calls_used = call.get_variable("calls_used") or 0
    calls_limit = call.get_variable("calls_limit") or 0
    plan = call.get_variable("plan") or "current"
    renewal_str = call.get_variable("renewal_str") or ""

    if outcome == "unavailable":
        logging.info("Unable to reach %s for usage alert on account %d", contact_name, account_id)
        try:
            log_usage_alert_outcome(account_id, "voicemail", "unknown")
        except Exception as e:
            logging.error("Failed to log outcome: %s", e)
        call.hangup(
            final_instructions=(
                f"Leave a brief voicemail for {contact_name} on behalf of Nexus Cloud. "
                f"Let them know their account has used {usage_pct}% of its monthly API quota "
                "and ask them to log in or call back if they have questions. Keep it brief."
            )
        )
    elif outcome == "available":
        calls_remaining = max(0, calls_limit - calls_used)
        renewal_note = f" Your limit resets on {renewal_str}." if renewal_str else ""

        call.set_task(
            "handle_response",
            objective=(
                f"Alert {contact_name} at {account_name or 'their company'} that their "
                f"Nexus Cloud account has used {usage_pct}% of its monthly API quota "
                f"({calls_used:,} of {calls_limit:,} calls). "
                "Understand if they're concerned and whether they'd like to upgrade their plan."
            ),
            checklist=[
                guava.Say(
                    f"Hi {contact_name}, this is Casey from Nexus Cloud. "
                    f"I'm calling with a quick heads-up: your account has used {usage_pct}% "
                    f"of your monthly API call limit — {calls_used:,} of {calls_limit:,} calls. "
                    f"You have {calls_remaining:,} calls remaining this month.{renewal_note} "
                    "I wanted to make sure you're aware before you hit the limit."
                ),
                guava.Field(
                    key="aware_of_usage",
                    field_type="multiple_choice",
                    description="Ask if they were aware their usage was this high.",
                    choices=["yes, we've been busy", "no, this is surprising"],
                    required=True,
                ),
                guava.Field(
                    key="concern_level",
                    field_type="multiple_choice",
                    description=(
                        "Ask how concerned they are about hitting the limit before the reset."
                    ),
                    choices=[
                        "very concerned/likely to hit it",
                        "somewhat concerned",
                        "not concerned/should be fine",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="upgrade_interest",
                    field_type="multiple_choice",
                    description=(
                        "If they're concerned, ask if they'd like to discuss upgrading their plan "
                        f"for a higher limit. Their current plan is {plan}."
                    ),
                    choices=[
                        "yes/interested in upgrading",
                        "maybe/send me info",
                        "no/we'll manage",
                    ],
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("handle_response")
def on_done(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    account_id = int(call.get_variable("account_id"))
    concern = call.get_field("concern_level") or "not concerned"
    intent = call.get_field("upgrade_interest") or "no"

    logging.info(
        "Usage alert handled for account %d — concern: %s, upgrade intent: %s",
        account_id, concern, intent,
    )

    try:
        outcome = "reached" if "concerned" in concern else "not_concerned"
        log_usage_alert_outcome(account_id, outcome, intent)
    except Exception as e:
        logging.error("Failed to log usage alert outcome for account %d: %s", account_id, e)

    if "upgrading" in intent:
        call.hangup(
            final_instructions=(
                f"Thank {contact_name} for their interest in upgrading. "
                "Let them know an account manager will reach out by email within a few hours "
                "with plan options and pricing. "
                "Assure them that upgrading takes effect immediately so they won't lose service. "
                "Thank them for being a Nexus Cloud customer."
            )
        )
    elif "send me info" in intent:
        call.hangup(
            final_instructions=(
                f"Let {contact_name} know you'll have the team send over information "
                "about higher-tier plans by email today. "
                "Remind them of their remaining calls and reset date. "
                "Thank them for their time."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {contact_name} for their time. "
                "Let them know we'll keep an eye on their usage and reach out again "
                "if they get within 5% of the limit. "
                "Remind them they can always upgrade through the dashboard or by calling us. "
                "Wish them a great day."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound usage alert call for a Nexus Cloud account near its API limit."
    )
    parser.add_argument("phone", help="Contact's phone number (E.164, e.g. +15551234567)")
    parser.add_argument("--account-id", required=True, type=int, help="Account ID in the database")
    parser.add_argument("--name", required=True, help="Contact's full name")
    args = parser.parse_args()

    logging.info(
        "Initiating usage alert call to %s (%s) for account %d",
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
