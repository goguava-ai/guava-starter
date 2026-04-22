import logging
import os
from datetime import datetime, timezone

import guava
import requests
from guava import logging_utils

STRIPE_SECRET_KEY = os.environ["STRIPE_SECRET_KEY"]
AUTH = (STRIPE_SECRET_KEY, "")
BASE_URL = "https://api.stripe.com"


def search_customer_by_email(email: str) -> dict | None:
    resp = requests.get(
        f"{BASE_URL}/v1/customers/search",
        auth=AUTH,
        params={"query": f'email:"{email}"', "limit": 1},
        timeout=10,
    )
    resp.raise_for_status()
    results = resp.json().get("data", [])
    return results[0] if results else None


def list_recent_charges(customer_id: str, limit: int = 5) -> list:
    """Returns recent succeeded charges for the customer, most recent first."""
    resp = requests.get(
        f"{BASE_URL}/v1/charges",
        auth=AUTH,
        params={"customer": customer_id, "limit": limit},
        timeout=10,
    )
    resp.raise_for_status()
    charges = resp.json().get("data", [])
    return [c for c in charges if c.get("status") == "succeeded" and not c.get("refunded")]


def create_refund(charge_id: str, reason: str) -> dict:
    """Creates a full refund for the given charge."""
    resp = requests.post(
        f"{BASE_URL}/v1/refunds",
        auth=AUTH,
        data={"charge": charge_id, "reason": reason},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def format_charge(charge: dict) -> str:
    """Returns a short human-readable description of a charge for the agent to read."""
    amount = charge.get("amount", 0) / 100
    currency = charge.get("currency", "usd").upper()
    description = charge.get("description") or charge.get("statement_descriptor") or "charge"
    created = datetime.fromtimestamp(charge["created"], tz=timezone.utc).strftime("%B %d, %Y")
    return f"${amount:,.2f} {currency} on {created} for '{description}'"


agent = guava.Agent(
    name="Morgan",
    organization="Luminary",
    purpose=(
        "to help Luminary customers request refunds for recent charges on their account"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "find_charge_and_refund",
        objective=(
            "A customer has called to request a refund. Verify their identity via email, "
            "look up their recent charges, confirm which charge they want refunded "
            "and the reason, then process the refund."
        ),
        checklist=[
            guava.Say(
                "Thanks for calling Luminary. I'm Morgan. I can help you with a refund. "
                "Let me pull up your account."
            ),
            guava.Field(
                key="caller_email",
                field_type="text",
                description="Ask for their email address on file.",
                required=True,
            ),
            guava.Field(
                key="refund_reason",
                field_type="multiple_choice",
                description=(
                    "Ask why they're requesting a refund. "
                    "Map their answer to one of these options."
                ),
                choices=["duplicate charge", "fraudulent charge", "other"],
                required=True,
            ),
        ],
    )


@agent.on_task_complete("find_charge_and_refund")
def find_charge_and_refund(call: guava.Call) -> None:
    email = call.get_field("caller_email") or ""
    reason_spoken = call.get_field("refund_reason") or "other"

    reason_map = {
        "duplicate charge": "duplicate",
        "fraudulent charge": "fraudulent",
        "other": "requested_by_customer",
    }
    stripe_reason = reason_map.get(reason_spoken, "requested_by_customer")

    logging.info("Processing refund request for email: %s, reason: %s", email, reason_spoken)

    try:
        customer = search_customer_by_email(email)
    except Exception as e:
        logging.error("Stripe search failed for %s: %s", email, e)
        customer = None

    if not customer:
        call.hangup(
            final_instructions=(
                "Let the caller know you couldn't find an account with that email address. "
                "Apologize and offer to transfer them to a billing specialist."
            )
        )
        return

    try:
        charges = list_recent_charges(customer["id"])
    except Exception as e:
        logging.error("Failed to list charges for %s: %s", customer["id"], e)
        charges = []

    if not charges:
        call.hangup(
            final_instructions=(
                "Let the caller know there are no recent refundable charges on their account. "
                "If they believe this is incorrect, offer to escalate to a billing specialist. "
                "Be apologetic and helpful."
            )
        )
        return

    # Always refund the most recent eligible charge
    charge = charges[0]
    charge_id = charge["id"]
    charge_description = format_charge(charge)

    logging.info("Issuing refund for charge %s (%s)", charge_id, charge_description)

    try:
        refund = create_refund(charge_id, stripe_reason)
        refund_id = refund["id"]
        name = customer.get("name") or "there"
        logging.info("Refund %s created for charge %s", refund_id, charge_id)
        call.hangup(
            final_instructions=(
                f"Let {name} know their refund has been processed successfully. "
                f"The refund is for {charge_description}. "
                "Let them know it typically takes 5–10 business days to appear on their statement, "
                "depending on their bank. "
                "Thank them for their patience and for being a Luminary customer."
            )
        )
    except Exception as e:
        logging.error("Failed to create refund for charge %s: %s", charge_id, e)
        call.hangup(
            final_instructions=(
                "Apologize for a technical issue processing the refund. "
                "Let the caller know their request has been escalated to our billing team "
                "and they'll receive a confirmation email within one business day. "
                "Thank them for their patience."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
