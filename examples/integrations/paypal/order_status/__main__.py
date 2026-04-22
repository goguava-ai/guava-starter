import guava
import os
import logging
from guava import logging_utils
import requests


BASE_URL = os.environ.get("PAYPAL_BASE_URL", "https://api-m.sandbox.paypal.com")


def get_access_token() -> str:
    resp = requests.post(
        f"{BASE_URL}/v1/oauth2/token",
        data={"grant_type": "client_credentials"},
        auth=(os.environ["PAYPAL_CLIENT_ID"], os.environ["PAYPAL_CLIENT_SECRET"]),
        headers={"Accept": "application/json"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def get_order(order_id: str, headers: dict) -> dict | None:
    resp = requests.get(f"{BASE_URL}/v2/checkout/orders/{order_id}", headers=headers, timeout=10)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def format_amount(amount: dict) -> str:
    value = amount.get("value", "")
    currency = amount.get("currency_code", "USD")
    return f"${value} {currency}"


agent = guava.Agent(
    name="Alex",
    organization="Northgate Commerce",
    purpose=(
        "to help Northgate Commerce customers check the status of their PayPal orders"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "lookup_order",
        objective=(
            "A customer has called to check on the status of a recent PayPal order. "
            "Verify their identity with their email and look up the order ID they provide."
        ),
        checklist=[
            guava.Say(
                "Thanks for calling Northgate Commerce. This is Alex. "
                "I can help you check on a PayPal order today."
            ),
            guava.Field(
                key="email",
                field_type="text",
                description="Ask for the email address associated with their PayPal order.",
                required=True,
            ),
            guava.Field(
                key="order_id",
                field_type="text",
                description=(
                    "Ask for their PayPal order ID. "
                    "Let them know it starts with a series of numbers and letters, "
                    "and they can find it in their PayPal confirmation email."
                ),
                required=True,
            ),
        ],
    )


@agent.on_task_complete("lookup_order")
def on_done(call: guava.Call) -> None:
    email = call.get_field("email") or ""
    order_id = (call.get_field("order_id") or "").strip()

    logging.info("Looking up PayPal order %s for %s", order_id, email)

    try:
        token = get_access_token()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        order = get_order(order_id, headers)
    except Exception as e:
        logging.error("PayPal order lookup failed: %s", e)
        order = None

    if not order:
        call.hangup(
            final_instructions=(
                f"Let the caller know we couldn't find an order with ID '{order_id}'. "
                "Ask them to double-check the order ID in their confirmation email. "
                "If the issue persists, they can visit paypal.com to view their activity. "
                "Be apologetic and helpful."
            )
        )
        return

    status = order.get("status", "UNKNOWN")
    purchase_units = order.get("purchase_units", [])
    total_str = ""
    if purchase_units:
        amount = purchase_units[0].get("amount", {})
        total_str = format_amount(amount)

    create_time = order.get("create_time", "")

    status_map = {
        "CREATED": "created but not yet paid",
        "SAVED": "saved",
        "APPROVED": "approved by the payer and pending capture",
        "VOIDED": "voided",
        "COMPLETED": "completed and payment captured",
        "PAYER_ACTION_REQUIRED": "waiting for payer action",
    }
    status_display = status_map.get(status, status.lower())

    logging.info("Order %s status: %s", order_id, status)

    call.hangup(
        final_instructions=(
            f"Let the caller know their PayPal order {order_id} has a status of: {status_display}. "
            + (f"The order total is {total_str}. " if total_str else "")
            + (f"It was created on {create_time[:10]}. " if create_time else "")
            + "If they have concerns about a completed charge or need a refund, "
            "let them know they can call back and ask to initiate a refund request. "
            "Be helpful and thorough."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
