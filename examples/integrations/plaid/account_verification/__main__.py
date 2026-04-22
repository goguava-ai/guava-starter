import logging
import os

import guava
import requests
from guava import logging_utils

BASE_URL = os.environ.get("PLAID_BASE_URL", "https://sandbox.plaid.com")


def get_headers() -> dict:
    return {
        "PLAID-CLIENT-ID": os.environ["PLAID_CLIENT_ID"],
        "PLAID-SECRET": os.environ["PLAID_SECRET"],
        "Content-Type": "application/json",
    }


def get_accounts(access_token: str) -> list:
    resp = requests.post(
        f"{BASE_URL}/accounts/get",
        headers=get_headers(),
        json={"access_token": access_token},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("accounts", [])


def get_auth(access_token: str) -> dict:
    """Returns ACH routing and account numbers for linked accounts."""
    resp = requests.post(
        f"{BASE_URL}/auth/get",
        headers=get_headers(),
        json={"access_token": access_token},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def lookup_access_token(account_reference: str) -> str | None:
    """
    In production, look up the user's Plaid access_token from your database using an
    account reference (e.g., user ID, email, or account number). This is a placeholder.
    """
    return os.environ.get("PLAID_TEST_ACCESS_TOKEN")


agent = guava.Agent(
    name="Jordan",
    organization="ClearPath Banking",
    purpose=(
        "to help ClearPath Banking customers verify their linked bank account details"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "verify_account",
        objective=(
            "A caller wants to verify their linked bank account. "
            "Verify their identity and confirm the account details on file."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling ClearPath Banking. This is Jordan. "
                "I can help you verify your linked account today."
            ),
            guava.Field(
                key="account_holder_name",
                field_type="text",
                description="Ask for their full name as it appears on the account.",
                required=True,
            ),
            guava.Field(
                key="account_reference",
                field_type="text",
                description=(
                    "Ask for their ClearPath account number or the email address "
                    "linked to their account, so we can pull up their record."
                ),
                required=True,
            ),
        ],
    )


@agent.on_task_complete("verify_account")
def on_done(call: guava.Call) -> None:
    name = call.get_field("account_holder_name") or ""
    reference = call.get_field("account_reference") or ""

    logging.info("Verifying account for %s (reference: %s)", name, reference)

    access_token = lookup_access_token(reference)
    if not access_token:
        call.hangup(
            final_instructions=(
                f"Let {name} know we couldn't find a linked account under that reference. "
                "Ask them to double-check their account number or email. "
                "They can also visit their dashboard to connect a bank account. Be helpful."
            )
        )
        return

    accounts = []
    auth_data = {}
    try:
        accounts = get_accounts(access_token)
        auth_data = get_auth(access_token)
    except Exception as e:
        logging.error("Plaid account lookup failed: %s", e)

    if not accounts:
        call.hangup(
            final_instructions=(
                f"Apologize to {name} — we couldn't retrieve the account details right now. "
                "Ask them to try again later or contact support. Be apologetic."
            )
        )
        return

    # Build a safe summary (last 4 digits of account numbers only)
    summaries = []
    numbers = auth_data.get("numbers", {}).get("ach", [])
    number_map = {n.get("account_id"): n for n in numbers}

    for acct in accounts[:3]:
        acct_id = acct.get("account_id", "")
        acct_type = acct.get("type", "")
        subtype = acct.get("subtype", "")
        institution_name = acct.get("official_name", "") or acct.get("name", "")
        mask = acct.get("mask", "****")
        balance = acct.get("balances", {}).get("current")
        balance_str = f"${balance:,.2f}" if balance is not None else "balance unavailable"
        routing = number_map.get(acct_id, {}).get("routing", "")

        summaries.append(
            f"{institution_name or acct_type} {subtype} account ending in {mask}, "
            f"current balance: {balance_str}"
            + (f", routing number: {routing}" if routing else "")
        )

    logging.info("Found %d accounts for reference %s", len(accounts), reference)

    call.hangup(
        final_instructions=(
            f"Let {name} know we found the following linked account(s): {'; '.join(summaries)}. "
            "Confirm these are the correct accounts. If any changes are needed, direct them to their ClearPath dashboard. "
            "Thank them for calling and wish them a great day."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
