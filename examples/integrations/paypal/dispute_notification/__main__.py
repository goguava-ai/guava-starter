import guava
import os
import logging
from guava import logging_utils
import argparse
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


def get_dispute(dispute_id: str, headers: dict) -> dict | None:
    resp = requests.get(
        f"{BASE_URL}/v1/customer/disputes/{dispute_id}",
        headers=headers,
        timeout=10,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


class DisputeNotificationController(guava.CallController):
    def __init__(self, customer_name: str, dispute_id: str):
        super().__init__()
        self.customer_name = customer_name
        self.dispute_id = dispute_id
        self.dispute = None

        try:
            token = get_access_token()
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            self.dispute = get_dispute(dispute_id, headers)
            logging.info(
                "Dispute %s loaded: status=%s",
                dispute_id,
                self.dispute.get("status") if self.dispute else "not found",
            )
        except Exception as e:
            logging.error("Failed to load dispute %s: %s", dispute_id, e)

        self.set_persona(
            organization_name="Northgate Commerce",
            agent_name="Alex",
            agent_purpose=(
                "to notify customers about open PayPal disputes and help them understand their options"
            ),
        )

        self.reach_person(
            contact_full_name=self.customer_name,
            on_success=self.notify_dispute,
            on_failure=self.leave_voicemail,
        )

    def notify_dispute(self):
        reason = "unknown"
        amount_str = ""
        status = "open"

        if self.dispute:
            reason = self.dispute.get("reason", "UNKNOWN").replace("_", " ").lower()
            status = self.dispute.get("status", "open").replace("_", " ").lower()
            disputed_amount = self.dispute.get("disputed_amount", {})
            if disputed_amount.get("value"):
                amount_str = f"${disputed_amount['value']} {disputed_amount.get('currency_code', 'USD')}"

        self.set_task(
            objective=(
                f"Notify {self.customer_name} about an open PayPal dispute on their account. "
                "Explain the dispute, collect their preferred resolution, and provide next steps."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.customer_name}, this is Alex calling from Northgate Commerce. "
                    f"I'm reaching out because there's an open PayPal dispute on your account "
                    f"(dispute ID: {self.dispute_id}) — the reason listed is '{reason}'"
                    + (f" for {amount_str}" if amount_str else "")
                    + ". I wanted to reach out personally to understand the situation and help resolve it."
                ),
                guava.Field(
                    key="aware",
                    field_type="multiple_choice",
                    description="Ask if they were aware of this dispute.",
                    choices=["yes, I filed it", "no, I didn't file it"],
                    required=True,
                ),
                guava.Field(
                    key="resolution_preference",
                    field_type="multiple_choice",
                    description=(
                        "Ask how they'd like to resolve the dispute. "
                        "If they filed it, ask if they'd like a refund, replacement, or to keep the dispute open. "
                        "If they didn't file it, let them know we'll investigate and flag potential fraud."
                    ),
                    choices=["refund preferred", "replacement preferred", "keep dispute open", "investigating fraud"],
                    required=True,
                ),
            ],
            on_complete=self.handle_resolution,
        )

    def handle_resolution(self):
        aware = self.get_field("aware") or ""
        preference = self.get_field("resolution_preference") or ""

        logging.info(
            "Dispute %s — customer aware: %s, preference: %s",
            self.dispute_id, aware, preference,
        )

        if "fraud" in preference or "didn't file" in aware:
            self.hangup(
                final_instructions=(
                    f"Let {self.customer_name} know you've flagged their account for a potential unauthorized "
                    "dispute. Our team will investigate within one business day and they'll receive an email "
                    "update. Recommend they also report the dispute to PayPal. Apologize for the inconvenience "
                    "and thank them for flagging it."
                )
            )
        elif "refund" in preference:
            self.hangup(
                final_instructions=(
                    f"Let {self.customer_name} know you've noted their preference for a refund. "
                    "Let them know our team will review the dispute and process a refund within "
                    "3–5 business days if eligible. They'll receive a PayPal notification. "
                    "Thank them for their patience and wish them a great day."
                )
            )
        elif "replacement" in preference:
            self.hangup(
                final_instructions=(
                    f"Let {self.customer_name} know you've noted their preference for a replacement. "
                    "Our fulfillment team will reach out by email within one business day with next steps. "
                    "Thank them and wish them a great day."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Let {self.customer_name} know the dispute (ID: {self.dispute_id}) remains open. "
                    "PayPal will continue to mediate, and they'll receive updates via email. "
                    "Thank them for taking the time to talk and wish them a great day."
                )
            )

    def leave_voicemail(self):
        logging.info("Unable to reach %s for dispute notification.", self.customer_name)
        self.hangup(
            final_instructions=(
                f"Leave a professional voicemail for {self.customer_name} from Northgate Commerce. "
                f"Let them know you're calling about an open PayPal dispute (ID: {self.dispute_id}) "
                "and ask them to call back or check their email for details. "
                "Keep it brief and non-alarming."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(description="Outbound PayPal dispute notification call.")
    parser.add_argument("phone", help="Customer phone number (E.164)")
    parser.add_argument("--name", required=True, help="Customer's full name")
    parser.add_argument("--dispute-id", required=True, help="PayPal dispute ID (PP-D-...)")
    args = parser.parse_args()

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=DisputeNotificationController(
            customer_name=args.name,
            dispute_id=args.dispute_id,
        ),
    )
