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


agent = guava.Agent(
    name="Alex",
    organization="Northgate Commerce",
    purpose=(
        "to notify customers about open PayPal disputes and help them understand their options"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    dispute_id = call.get_variable("dispute_id")

    call.customer_name = customer_name
    call.dispute_id = dispute_id
    call.dispute = None

    try:
        token = get_access_token()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        call.dispute = get_dispute(dispute_id, headers)
        logging.info(
            "Dispute %s loaded: status=%s",
            dispute_id,
            call.dispute.get("status") if call.dispute else "not found",
        )
    except Exception as e:
        logging.error("Failed to load dispute %s: %s", dispute_id, e)

    call.reach_person(contact_full_name=customer_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    if outcome == "unavailable":
        logging.info("Unable to reach %s for dispute notification.", call.customer_name)
        call.hangup(
            final_instructions=(
                f"Leave a professional voicemail for {call.customer_name} from Northgate Commerce. "
                f"Let them know you're calling about an open PayPal dispute (ID: {call.dispute_id}) "
                "and ask them to call back or check their email for details. "
                "Keep it brief and non-alarming."
            )
        )
    elif outcome == "available":
        reason = "unknown"
        amount_str = ""
        status = "open"

        if call.dispute:
            reason = call.dispute.get("reason", "UNKNOWN").replace("_", " ").lower()
            status = call.dispute.get("status", "open").replace("_", " ").lower()
            disputed_amount = call.dispute.get("disputed_amount", {})
            if disputed_amount.get("value"):
                amount_str = f"${disputed_amount['value']} {disputed_amount.get('currency_code', 'USD')}"

        call.set_task(
            "handle_resolution",
            objective=(
                f"Notify {call.customer_name} about an open PayPal dispute on their account. "
                "Explain the dispute, collect their preferred resolution, and provide next steps."
            ),
            checklist=[
                guava.Say(
                    f"Hi {call.customer_name}, this is Alex calling from Northgate Commerce. "
                    f"I'm reaching out because there's an open PayPal dispute on your account "
                    f"(dispute ID: {call.dispute_id}) — the reason listed is '{reason}'"
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
        )


@agent.on_task_complete("handle_resolution")
def on_done(call: guava.Call) -> None:
    aware = call.get_field("aware") or ""
    preference = call.get_field("resolution_preference") or ""

    logging.info(
        "Dispute %s — customer aware: %s, preference: %s",
        call.dispute_id, aware, preference,
    )

    if "fraud" in preference or "didn't file" in aware:
        call.hangup(
            final_instructions=(
                f"Let {call.customer_name} know you've flagged their account for a potential unauthorized "
                "dispute. Our team will investigate within one business day and they'll receive an email "
                "update. Recommend they also report the dispute to PayPal. Apologize for the inconvenience "
                "and thank them for flagging it."
            )
        )
    elif "refund" in preference:
        call.hangup(
            final_instructions=(
                f"Let {call.customer_name} know you've noted their preference for a refund. "
                "Let them know our team will review the dispute and process a refund within "
                "3–5 business days if eligible. They'll receive a PayPal notification. "
                "Thank them for their patience and wish them a great day."
            )
        )
    elif "replacement" in preference:
        call.hangup(
            final_instructions=(
                f"Let {call.customer_name} know you've noted their preference for a replacement. "
                "Our fulfillment team will reach out by email within one business day with next steps. "
                "Thank them and wish them a great day."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Let {call.customer_name} know the dispute (ID: {call.dispute_id}) remains open. "
                "PayPal will continue to mediate, and they'll receive updates via email. "
                "Thank them for taking the time to talk and wish them a great day."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(description="Outbound PayPal dispute notification call.")
    parser.add_argument("phone", help="Customer phone number (E.164)")
    parser.add_argument("--name", required=True, help="Customer's full name")
    parser.add_argument("--dispute-id", required=True, help="PayPal dispute ID (PP-D-...)")
    args = parser.parse_args()

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "customer_name": args.name,
            "dispute_id": args.dispute_id,
        },
    )
