import guava
import os
import logging
from guava import logging_utils
import requests


BASE_URL = os.environ.get("PLAID_BASE_URL", "https://sandbox.plaid.com")


def get_headers() -> dict:
    return {
        "PLAID-CLIENT-ID": os.environ["PLAID_CLIENT_ID"],
        "PLAID-SECRET": os.environ["PLAID_SECRET"],
        "Content-Type": "application/json",
    }


def get_balance(access_token: str) -> list:
    """Returns real-time balance data for all accounts linked to the access token."""
    resp = requests.post(
        f"{BASE_URL}/accounts/balance/get",
        headers=get_headers(),
        json={"access_token": access_token},
        timeout=15,  # balance calls may be slower (real-time fetch from institution)
    )
    resp.raise_for_status()
    return resp.json().get("accounts", [])


def lookup_access_token(reference: str) -> str | None:
    return os.environ.get("PLAID_TEST_ACCESS_TOKEN")


agent = guava.Agent(
    name="Jordan",
    organization="ClearPath Banking",
    purpose="to help ClearPath Banking customers check their current account balance",
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "get_balance",
        objective=(
            "A caller wants to check their current bank account balance. "
            "Verify their identity and look up their real-time balance."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling ClearPath Banking. This is Jordan. "
                "I can check your current balance today."
            ),
            guava.Field(
                key="name",
                field_type="text",
                description="Ask for their full name.",
                required=True,
            ),
            guava.Field(
                key="reference",
                field_type="text",
                description="Ask for their ClearPath account number or registered email.",
                required=True,
            ),
            guava.Field(
                key="account_preference",
                field_type="multiple_choice",
                description=(
                    "Ask which account they want to check: checking, savings, or all accounts."
                ),
                choices=["checking", "savings", "all accounts"],
                required=True,
            ),
        ],
    )


@agent.on_task_complete("get_balance")
def on_done(call: guava.Call) -> None:
    name = call.get_field("name") or ""
    reference = call.get_field("reference") or ""
    preference = call.get_field("account_preference") or "all accounts"

    logging.info("Balance inquiry for %s (preference: %s)", name, preference)

    access_token = lookup_access_token(reference)
    if not access_token:
        call.hangup(
            final_instructions=(
                f"Let {name} know we couldn't find an account under that reference. "
                "Ask them to double-check their account number or email. Be apologetic."
            )
        )
        return

    accounts = []
    try:
        accounts = get_balance(access_token)
    except Exception as e:
        logging.error("Balance fetch failed: %s", e)

    if not accounts:
        call.hangup(
            final_instructions=(
                f"Apologize to {name} — we couldn't retrieve the balance right now. "
                "Ask them to try again in a few minutes or log into their dashboard."
            )
        )
        return

    # Filter by account type preference
    if preference in ("checking", "savings"):
        filtered = [a for a in accounts if a.get("subtype", "").lower() == preference]
        if not filtered:
            filtered = accounts  # fallback to all if no match
    else:
        filtered = accounts

    balance_summaries = []
    for acct in filtered[:3]:
        subtype = acct.get("subtype", acct.get("type", "account"))
        mask = acct.get("mask", "****")
        balances = acct.get("balances", {})
        current = balances.get("current")
        available = balances.get("available")

        balance_str = f"${current:,.2f}" if current is not None else "unavailable"
        avail_str = f"${available:,.2f}" if available is not None else ""

        summary = f"{subtype} account ending in {mask}: current balance {balance_str}"
        if avail_str:
            summary += f", available {avail_str}"
        balance_summaries.append(summary)

    logging.info("Returning balance for %d account(s) to %s", len(filtered), name)

    call.hangup(
        final_instructions=(
            f"Let {name} know their account balance{'s are' if len(balance_summaries) > 1 else ' is'}: "
            f"{'; '.join(balance_summaries)}. "
            "Answer any follow-up questions they have. "
            "Remind them they can also check their balance anytime in the ClearPath app. "
            "Thank them for calling and wish them a great day."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
