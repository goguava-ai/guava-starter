import guava
import os
import logging
from guava import logging_utils
import uuid
import requests


BASE_URL = os.environ.get("SQUARE_BASE_URL", "https://connect.squareupsandbox.com")
SQUARE_VERSION = "2024-01-18"


def get_headers() -> dict:
    return {
        "Authorization": f"Bearer {os.environ['SQUARE_ACCESS_TOKEN']}",
        "Square-Version": SQUARE_VERSION,
        "Content-Type": "application/json",
    }


def get_payment(payment_id: str) -> dict | None:
    resp = requests.get(
        f"{BASE_URL}/v2/payments/{payment_id}",
        headers=get_headers(),
        timeout=10,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json().get("payment")


def create_refund(payment_id: str, amount_money: dict, reason: str) -> dict | None:
    resp = requests.post(
        f"{BASE_URL}/v2/refunds",
        headers=get_headers(),
        json={
            "idempotency_key": str(uuid.uuid4()),
            "payment_id": payment_id,
            "amount_money": amount_money,
            "reason": reason,
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("refund")


def format_amount(amount_money: dict) -> str:
    amount = amount_money.get("amount", 0)
    currency = amount_money.get("currency", "USD")
    return f"${amount / 100:,.2f} {currency}"


agent = guava.Agent(
    name="Drew",
    organization="Harbor Market",
    purpose="to help Harbor Market customers request refunds on Square payments",
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "process_refund",
        objective=(
            "A customer has called to request a refund on a Square payment. "
            "Collect the payment ID, verify the payment, and process the refund."
        ),
        checklist=[
            guava.Say(
                "Thanks for calling Harbor Market. This is Drew. "
                "I can help you with a refund today."
            ),
            guava.Field(
                key="payment_id",
                field_type="text",
                description=(
                    "Ask for their payment or transaction ID. "
                    "It's a long alphanumeric string they can find in their email receipt."
                ),
                required=True,
            ),
            guava.Field(
                key="refund_reason",
                field_type="multiple_choice",
                description="Ask why they're requesting the refund.",
                choices=["item not received", "item damaged or defective", "not as described", "changed my mind", "duplicate charge"],
                required=True,
            ),
            guava.Field(
                key="full_or_partial",
                field_type="multiple_choice",
                description="Ask whether they'd like a full refund or partial refund.",
                choices=["full refund", "partial refund"],
                required=True,
            ),
            guava.Field(
                key="confirmed",
                field_type="multiple_choice",
                description="Confirm they'd like to proceed with the refund.",
                choices=["yes, proceed", "no, cancel"],
                required=True,
            ),
        ],
    )


@agent.on_task_complete("process_refund")
def process_refund(call: guava.Call) -> None:
    payment_id = (call.get_field("payment_id") or "").strip()
    reason = call.get_field("refund_reason") or ""
    confirmed = call.get_field("confirmed") or ""

    if "cancel" in confirmed or "no" in confirmed:
        call.hangup(
            final_instructions=(
                "Let the caller know the refund request has been cancelled. "
                "Thank them for calling and wish them a great day."
            )
        )
        return

    logging.info("Processing Square refund for payment %s, reason: %s", payment_id, reason)

    try:
        payment = get_payment(payment_id)
    except Exception as e:
        logging.error("Payment lookup failed: %s", e)
        payment = None

    if not payment:
        call.hangup(
            final_instructions=(
                f"Apologize — we couldn't find a payment with ID '{payment_id}'. "
                "Ask the caller to check their receipt email for the correct transaction ID. "
                "They can also visit us in store for assistance. Be helpful and apologetic."
            )
        )
        return

    status = payment.get("status", "")
    if status not in ("COMPLETED",):
        call.hangup(
            final_instructions=(
                f"Let the caller know their payment has a status of '{status}' and cannot be refunded "
                "at this time. Ask them to contact us in store if they believe this is an error."
            )
        )
        return

    amount_money = payment.get("amount_money", {})
    amount_str = format_amount(amount_money)

    refund = None
    try:
        refund = create_refund(payment_id, amount_money, f"Customer request: {reason}")
        logging.info("Refund created: %s", refund.get("id") if refund else None)
    except Exception as e:
        logging.error("Refund creation failed: %s", e)

    if refund and refund.get("status") in ("PENDING", "COMPLETED"):
        call.hangup(
            final_instructions=(
                f"Let the caller know their refund of {amount_str} has been submitted successfully. "
                "Refunds typically appear in 3–5 business days depending on their bank. "
                "They'll receive an email receipt from Square. Thank them and wish them a great day."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                "Apologize — the refund couldn't be processed automatically. "
                "Let them know our team will review and process the refund manually within one business day. "
                "Thank them for their patience."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
