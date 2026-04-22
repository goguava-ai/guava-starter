import logging
import os
from datetime import datetime, timedelta, timezone

import guava
import requests
from guava import logging_utils

BASE_URL = "https://sandbox.plaid.com"


def get_headers() -> dict:
    return {
        "Content-Type": "application/json",
        "PLAID-CLIENT-ID": os.environ["PLAID_CLIENT_ID"],
        "PLAID-SECRET": os.environ["PLAID_SECRET"],
    }


def lookup_access_token(user_id: str) -> str | None:
    """Placeholder: retrieve the Plaid access_token for this user from your database."""
    raise NotImplementedError("Replace with a real DB lookup for the user's Plaid access_token.")


def get_transactions(access_token: str, days: int = 30) -> list[dict]:
    """Fetches recent transactions using /transactions/get."""
    start_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    payload = {
        "access_token": access_token,
        "start_date": start_date,
        "end_date": end_date,
        "options": {"count": 50, "offset": 0},
    }
    resp = requests.post(f"{BASE_URL}/transactions/get", headers=get_headers(), json=payload, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    return data.get("transactions", [])


def summarize_transactions(transactions: list[dict]) -> dict:
    total_spent = sum(t["amount"] for t in transactions if t["amount"] > 0)
    total_received = abs(sum(t["amount"] for t in transactions if t["amount"] < 0))
    largest = max(transactions, key=lambda t: t["amount"]) if transactions else None
    categories: dict[str, float] = {}
    for t in transactions:
        cat = t.get("category", ["Other"])[0] if t.get("category") else "Other"
        categories[cat] = categories.get(cat, 0) + max(t["amount"], 0)
    top_category = max(categories, key=lambda k: categories[k]) if categories else "N/A"
    return {
        "count": len(transactions),
        "total_spent": round(total_spent, 2),
        "total_received": round(total_received, 2),
        "largest_amount": largest["amount"] if largest else 0,
        "largest_name": largest["name"] if largest else "N/A",
        "top_category": top_category,
    }


agent = guava.Agent(
    name="Jordan",
    organization="ClearPath Banking",
    purpose="to help ClearPath Banking customers review their recent transactions",
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


DAYS = 30


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    user_id = call.get_variable("user_id")
    transactions: list[dict] = []
    summary: dict = {}

    try:
        access_token = lookup_access_token(user_id)
        if access_token:
            transactions = get_transactions(access_token, days=DAYS)
            summary = summarize_transactions(transactions)
            logging.info("Loaded %d transactions for user %s", len(transactions), user_id)
    except Exception as e:
        logging.error("Failed to load transactions: %s", e)

    call.set_variable("transactions", transactions)
    call.set_variable("summary", summary)

    context = (
        f"The customer has {summary.get('count', 0)} transactions in the past {DAYS} days. "
        f"Total spent: ${summary.get('total_spent', 0):.2f}. "
        f"Largest transaction: ${summary.get('largest_amount', 0):.2f} at {summary.get('largest_name', 'N/A')}. "
        f"Top spending category: {summary.get('top_category', 'N/A')}."
        if summary
        else "Transaction data could not be loaded."
    )

    call.set_task(
        "review_transactions",
        objective=(
            "A customer has called to review their recent transaction history. "
            f"Here is a summary of their activity: {context} "
            "Walk them through their spending summary and answer any questions they have."
        ),
        checklist=[
            guava.Say(
                "Welcome to ClearPath Banking. This is Jordan. I can walk you through your recent transactions."
            ),
            guava.Field(
                key="review_period",
                field_type="multiple_choice",
                description="Ask if they'd like to hear their summary for the past 30 days, or if they have a specific concern.",
                choices=["summary", "specific transaction", "dispute a charge"],
                required=True,
            ),
            guava.Field(
                key="specific_concern",
                field_type="text",
                description=(
                    "If they have a specific concern or want to find a particular transaction, "
                    "ask them to describe it (merchant name, approximate amount, or date)."
                ),
                required=False,
            ),
        ],
    )


@agent.on_task_complete("review_transactions")
def on_done(call: guava.Call) -> None:
    review_period = call.get_field("review_period") or "summary"
    specific_concern = call.get_field("specific_concern") or ""
    summary = call.get_variable("summary") or {}
    transactions = call.get_variable("transactions") or []

    if review_period == "dispute a charge":
        call.hangup(
            final_instructions=(
                "Let the customer know that to dispute a charge, they should visit the ClearPath Banking app "
                "or call back and say 'dispute' to reach the disputes team directly. "
                "Thank them for calling."
            )
        )
        return

    if specific_concern and transactions:
        concern_lower = specific_concern.lower()
        matches = [
            t for t in transactions
            if concern_lower in t.get("name", "").lower()
            or concern_lower in (t.get("category") or [""])[0].lower()
        ]
        match_text = ""
        if matches:
            top = matches[:3]
            match_text = " Matching transactions found: " + "; ".join(
                f"{t['name']} ${t['amount']:.2f} on {t['date']}" for t in top
            )
        else:
            match_text = " No transactions matching that description were found in the past 30 days."

        call.hangup(
            final_instructions=(
                f"Tell the customer: {match_text} "
                "Thank them for banking with ClearPath."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Read the following transaction summary to the customer: "
                f"In the past {DAYS} days you had {summary.get('count', 0)} transactions. "
                f"Total spent: ${summary.get('total_spent', 0):.2f}. "
                f"Your largest purchase was ${summary.get('largest_amount', 0):.2f} at {summary.get('largest_name', 'N/A')}. "
                f"Your top spending category was {summary.get('top_category', 'N/A')}. "
                "Ask if there's anything else they'd like to review. Thank them for banking with ClearPath."
            )
        )

if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
