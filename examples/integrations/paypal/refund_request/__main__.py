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


def get_capture_id(order: dict) -> str | None:
    """Extracts the capture ID from a completed PayPal order."""
    for unit in order.get("purchase_units", []):
        for capture in unit.get("payments", {}).get("captures", []):
            if capture.get("status") == "COMPLETED":
                return capture.get("id")
    return None


def create_refund(capture_id: str, note: str, headers: dict) -> dict | None:
    resp = requests.post(
        f"{BASE_URL}/v2/payments/captures/{capture_id}/refund",
        headers=headers,
        json={"note_to_payer": note},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


class RefundRequestController(guava.CallController):
    def __init__(self):
        super().__init__()
        self.headers = {}

        try:
            token = get_access_token()
            self.headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        except Exception as e:
            logging.error("Failed to get PayPal token: %s", e)

        self.set_persona(
            organization_name="Northgate Commerce",
            agent_name="Alex",
            agent_purpose="to help Northgate Commerce customers request refunds on PayPal orders",
        )

        self.set_task(
            objective=(
                "A customer has called to request a refund on a PayPal order. "
                "Collect their order ID, verify it's eligible for a refund, and process it."
            ),
            checklist=[
                guava.Say(
                    "Thanks for calling Northgate Commerce. This is Alex. "
                    "I can help you with a refund request today."
                ),
                guava.Field(
                    key="order_id",
                    field_type="text",
                    description="Ask for their PayPal order ID.",
                    required=True,
                ),
                guava.Field(
                    key="refund_reason",
                    field_type="multiple_choice",
                    description="Ask why they're requesting the refund.",
                    choices=[
                        "item not received",
                        "item not as described",
                        "duplicate charge",
                        "changed my mind",
                        "other",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="refund_confirmed",
                    field_type="multiple_choice",
                    description="Confirm they'd like to proceed with the full refund.",
                    choices=["yes, proceed", "no, cancel"],
                    required=True,
                ),
            ],
            on_complete=self.process_refund,
        )

        self.accept_call()

    def process_refund(self):
        order_id = (self.get_field("order_id") or "").strip()
        reason = self.get_field("refund_reason") or ""
        confirmed = self.get_field("refund_confirmed") or ""

        if "cancel" in confirmed or "no" in confirmed:
            self.hangup(
                final_instructions=(
                    "Let the caller know the refund request has been cancelled and no action was taken. "
                    "Thank them for calling and wish them a great day."
                )
            )
            return

        logging.info("Processing refund for order %s, reason: %s", order_id, reason)

        try:
            order = get_order(order_id, self.headers)
        except Exception as e:
            logging.error("Order lookup failed for %s: %s", order_id, e)
            order = None

        if not order:
            self.hangup(
                final_instructions=(
                    f"Apologize — we couldn't find an order with ID '{order_id}'. "
                    "Ask the customer to double-check the ID from their PayPal confirmation email. "
                    "If they need more help, they can contact PayPal directly."
                )
            )
            return

        status = order.get("status", "")
        if status != "COMPLETED":
            self.hangup(
                final_instructions=(
                    f"Let the caller know their order has a status of '{status}' and cannot be refunded "
                    "at this time. Only completed, captured orders are eligible. "
                    "Ask them to contact support if they believe this is an error."
                )
            )
            return

        capture_id = get_capture_id(order)
        if not capture_id:
            self.hangup(
                final_instructions=(
                    "Apologize — we couldn't find a completed payment on this order to refund. "
                    "Ask the customer to contact customer support for manual review. "
                    "Thank them for their patience."
                )
            )
            return

        refund = None
        try:
            refund = create_refund(capture_id, f"Customer refund: {reason}", self.headers)
            logging.info("Refund created: %s", refund.get("id") if refund else None)
        except Exception as e:
            logging.error("Refund creation failed for capture %s: %s", capture_id, e)

        if refund and refund.get("status") in ("COMPLETED", "PENDING"):
            self.hangup(
                final_instructions=(
                    f"Let the caller know their refund for order {order_id} has been successfully submitted. "
                    "PayPal typically processes refunds within 3–5 business days back to the original payment method. "
                    "They'll receive a confirmation email from PayPal. Thank them and wish them a great day."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    "Apologize — the refund couldn't be processed automatically. "
                    "Let them know our support team will review the request and follow up by email within one business day. "
                    "Thank them for their patience."
                )
            )


if __name__ == "__main__":
    logging_utils.configure_logging()
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=RefundRequestController,
    )
