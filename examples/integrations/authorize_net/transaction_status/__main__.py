import guava
import os
import logging
from guava import logging_utils
import requests
from datetime import datetime


API_LOGIN_ID = os.environ["AUTHNET_API_LOGIN_ID"]
TRANSACTION_KEY = os.environ["AUTHNET_TRANSACTION_KEY"]
BASE_URL = (
    "https://api.authorize.net/xml/v1/request.api"
    if os.environ.get("AUTHNET_ENVIRONMENT") == "production"
    else "https://apitest.authorize.net/xml/v1/request.api"
)


def authnet_credentials() -> dict:
    return {"name": API_LOGIN_ID, "transactionKey": TRANSACTION_KEY}


def api_call(payload: dict) -> dict:
    resp = requests.post(BASE_URL, json=payload, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    messages = data.get("messages", {})
    if messages.get("resultCode") == "Error":
        raise RuntimeError(
            f"Authorize.net error: {messages.get('message', [{}])[0].get('text', 'Unknown error')}"
        )
    return data


def get_transaction_details(trans_id: str) -> dict:
    payload = {
        "getTransactionDetailsRequest": {
            "merchantAuthentication": authnet_credentials(),
            "transId": trans_id,
        }
    }
    return api_call(payload)


STATUS_MAP = {
    "settledSuccessfully": "completed and settled",
    "authorizedPendingCapture": "authorized and pending capture",
    "declined": "declined",
    "voided": "voided",
    "refundSettledSuccessfully": "refunded and settled",
    "underReview": "currently under review",
    "pendingFinalSettlement": "pending final settlement",
    "failedReview": "failed review",
}


def friendly_status(raw_status: str) -> str:
    return STATUS_MAP.get(raw_status, raw_status.replace("_", " "))


def format_date(dt_str: str) -> str:
    """Parse an Authorize.net local datetime string like '2024-03-15T10:30:00' into a readable form."""
    try:
        dt = datetime.fromisoformat(dt_str)
        return dt.strftime("%B %d, %Y at %I:%M %p")
    except Exception:
        return dt_str


agent = guava.Agent(
    name="Alex",
    organization="Pinnacle Payments",
    purpose="to help Pinnacle Payments customers check the status of their transactions",
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "collect_transaction_info",
        objective=(
            "A customer has called to check whether a payment went through. "
            "Collect their email address and transaction ID, look up the transaction "
            "in Authorize.net, then read back the status, amount, and date submitted."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Pinnacle Payments. I'm Alex, and I'm here to help "
                "you check the status of a transaction. Let me pull that up for you."
            ),
            guava.Field(
                key="email",
                field_type="text",
                description="Ask for the customer's email address on file.",
                required=True,
            ),
            guava.Field(
                key="transaction_id",
                field_type="text",
                description=(
                    "Ask for their transaction ID — it's a string of numbers found in "
                    "their receipt email or bank statement reference."
                ),
                required=True,
            ),
        ],
    )


@agent.on_task_complete("collect_transaction_info")
def on_collect_done(call: guava.Call) -> None:
    email = call.get_field("email") or ""
    trans_id = (call.get_field("transaction_id") or "").strip()

    logging.info("Transaction status lookup — email: %s, transId: %s", email, trans_id)

    try:
        data = get_transaction_details(trans_id)
        txn = data.get("transaction", {})
    except Exception as e:
        logging.error("Failed to fetch transaction %s: %s", trans_id, e)
        call.hangup(
            final_instructions=(
                "Let the caller know you weren't able to retrieve that transaction. "
                "Ask them to double-check the transaction ID and try again, or offer to "
                "connect them with a billing specialist. Be apologetic and helpful."
            )
        )
        return

    if not txn:
        call.hangup(
            final_instructions=(
                "Let the caller know no transaction was found for that ID. "
                "Ask them to verify the transaction ID from their receipt email or bank statement. "
                "Offer to connect them with a billing specialist if needed."
            )
        )
        return

    raw_status = txn.get("transactionStatus", "unknown")
    status_str = friendly_status(raw_status)
    amount = txn.get("settleAmount", txn.get("authAmount", ""))
    submit_time = txn.get("submitTimeLocal", "")
    invoice_number = txn.get("order", {}).get("invoiceNumber", "")
    customer_email = txn.get("customer", {}).get("email", "")

    amount_str = f"${float(amount):,.2f}" if amount else "an unknown amount"
    date_str = format_date(submit_time) if submit_time else "an unknown date"
    invoice_note = f" with invoice number {invoice_number}" if invoice_number else ""

    logging.info(
        "Transaction %s — status: %s, amount: %s, submitted: %s",
        trans_id, raw_status, amount, submit_time,
    )

    call.set_task(
        "wrap_up_transaction",
        objective=(
            "You've retrieved the transaction details. Share them with the customer, "
            "then ask if they have any other questions."
        ),
        checklist=[
            guava.Say(
                f"I found your transaction{invoice_note}. "
                f"The payment of {amount_str} submitted on {date_str} is currently "
                f"{status_str}."
            ),
            guava.Field(
                key="has_other_questions",
                field_type="multiple_choice",
                description="Ask if there is anything else you can help them with today.",
                choices=["yes", "no"],
                required=True,
            ),
        ],
    )


@agent.on_task_complete("wrap_up_transaction")
def on_wrap_up_done(call: guava.Call) -> None:
    has_other_questions = call.get_field("has_other_questions") or "no"
    if "yes" in has_other_questions:
        call.hangup(
            final_instructions=(
                "The customer has indicated they need additional assistance. "
                "Connect them with a billing specialist who can address any other payment or account questions. "
                "Be friendly and helpful."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                "Thank the customer for calling Pinnacle Payments and wish them a great day. "
                "Keep it warm and brief."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
