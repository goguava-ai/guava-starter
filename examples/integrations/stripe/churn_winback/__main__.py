import guava
import os
import logging
from guava import logging_utils
import argparse
import requests
from datetime import datetime, timezone


STRIPE_SECRET_KEY = os.environ["STRIPE_SECRET_KEY"]
AUTH = (STRIPE_SECRET_KEY, "")
BASE_URL = "https://api.stripe.com"

# Optional: a Stripe coupon ID to attach to the customer if they're interested in returning.
WINBACK_COUPON_ID = os.environ.get("STRIPE_WINBACK_COUPON_ID", "")


def get_customer(customer_id: str) -> dict | None:
    resp = requests.get(f"{BASE_URL}/v1/customers/{customer_id}", auth=AUTH, timeout=10)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def list_canceled_subscriptions(customer_id: str) -> list:
    resp = requests.get(
        f"{BASE_URL}/v1/subscriptions",
        auth=AUTH,
        params={"customer": customer_id, "status": "canceled", "limit": 3},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("data", [])


def attach_winback_coupon(customer_id: str, coupon_id: str) -> None:
    """Attaches a coupon to the customer so it applies on their next invoice."""
    resp = requests.post(
        f"{BASE_URL}/v1/customers/{customer_id}",
        auth=AUTH,
        data={"coupon": coupon_id},
        timeout=10,
    )
    resp.raise_for_status()


def update_customer_metadata(customer_id: str, metadata: dict) -> None:
    data = {f"metadata[{k}]": v for k, v in metadata.items()}
    resp = requests.post(
        f"{BASE_URL}/v1/customers/{customer_id}",
        auth=AUTH,
        data=data,
        timeout=10,
    )
    resp.raise_for_status()


agent = guava.Agent(
    name="Sam",
    organization="Luminary",
    purpose=(
        "to reconnect with former Luminary customers and understand what would "
        "bring them back"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    customer_id = call.get_variable("customer_id")
    customer_name = call.get_variable("customer_name")

    plan_name = "your previous plan"
    canceled_date = ""

    try:
        subscriptions = list_canceled_subscriptions(customer_id)
        if subscriptions:
            sub = subscriptions[0]
            items = sub.get("items", {}).get("data", [])
            if items:
                price = items[0].get("price", {})
                plan_name = price.get("nickname") or price.get("id") or plan_name
            ended_at = sub.get("ended_at")
            if ended_at:
                canceled_date = datetime.fromtimestamp(ended_at, tz=timezone.utc).strftime("%B %d, %Y")
    except Exception as e:
        logging.error("Failed to fetch canceled subscriptions for %s: %s", customer_id, e)

    call.set_variable("plan_name", plan_name)
    call.set_variable("canceled_date", canceled_date)

    call.reach_person(contact_full_name=customer_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    customer_name = call.get_variable("customer_name")

    if outcome == "unavailable":
        logging.info("Unable to reach %s for churn winback", customer_name)
        call.hangup(
            final_instructions=(
                f"Leave a brief, warm voicemail for {customer_name} on behalf of Luminary. "
                "Let them know you were calling to check in after their cancellation and that "
                "you'll send a quick email. No action needed — just keep it friendly and brief."
            )
        )
    elif outcome == "available":
        canceled_date = call.get_variable("canceled_date")
        plan_name = call.get_variable("plan_name")
        date_note = f" on {canceled_date}" if canceled_date else " recently"

        call.set_task(
            "record_and_close",
            objective=(
                f"Reconnect with {customer_name}, a former Luminary customer who canceled "
                f"'{plan_name}'{date_note}. "
                "Understand why they left and gauge their interest in returning."
            ),
            checklist=[
                guava.Say(
                    f"Hi {customer_name}, this is Sam calling from Luminary. "
                    f"I noticed you canceled your subscription{date_note} and I wanted to "
                    "reach out personally — not to pressure you, but just to hear how things "
                    "went and see if there's anything we could have done better. "
                    "Do you have just a couple of minutes?"
                ),
                guava.Field(
                    key="primary_reason",
                    field_type="multiple_choice",
                    description="Ask what the main reason was for canceling.",
                    choices=[
                        "too expensive",
                        "missing a feature I needed",
                        "switched to a competitor",
                        "business closed or downsized",
                        "didn't use it enough",
                        "other",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="competitor",
                    field_type="text",
                    description=(
                        "If they switched to a competitor, ask who they moved to — "
                        "only if they're comfortable sharing. Skip if not applicable."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="what_would_bring_back",
                    field_type="text",
                    description=(
                        "Ask: 'Is there anything we could do or change that would make "
                        "Luminary worth reconsidering?' Capture their answer fully."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="interest_in_returning",
                    field_type="multiple_choice",
                    description="Ask how likely they are to give Luminary another try in the future.",
                    choices=["definitely interested", "maybe/need to think about it", "unlikely"],
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("record_and_close")
def record_and_close(call: guava.Call) -> None:
    customer_id = call.get_variable("customer_id")
    customer_name = call.get_variable("customer_name")
    reason = call.get_field("primary_reason") or "unknown"
    competitor = call.get_field("competitor") or ""
    what_would_bring_back = call.get_field("what_would_bring_back") or ""
    interest = call.get_field("interest_in_returning") or "unlikely"

    logging.info(
        "Churn winback complete for %s — reason: %s, interest: %s",
        customer_id, reason, interest,
    )

    metadata = {
        "winback_reason": reason,
        "winback_interest": interest,
        "winback_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }
    if competitor:
        metadata["winback_competitor"] = competitor
    if what_would_bring_back:
        metadata["winback_feedback"] = what_would_bring_back[:500]  # Stripe metadata limit

    try:
        update_customer_metadata(customer_id, metadata)

        # If they're interested in returning and a winback coupon is configured, attach it.
        if interest == "definitely interested" and WINBACK_COUPON_ID:
            attach_winback_coupon(customer_id, WINBACK_COUPON_ID)
            logging.info("Winback coupon %s attached to customer %s", WINBACK_COUPON_ID, customer_id)

    except Exception as e:
        logging.error("Failed to update customer %s metadata: %s", customer_id, e)

    if interest == "definitely interested":
        coupon_note = (
            " As a thank-you for your time, we've applied a discount to your account "
            "that will automatically be applied if you decide to resubscribe."
            if WINBACK_COUPON_ID
            else ""
        )
        call.hangup(
            final_instructions=(
                f"Thank {customer_name} warmly for their candid feedback. "
                + coupon_note
                + " Let them know a team member will follow up by email with information "
                "about what's new at Luminary. Express genuine excitement about the "
                "possibility of having them back. Wish them a great day."
            )
        )
    elif interest == "maybe/need to think about it":
        call.hangup(
            final_instructions=(
                f"Thank {customer_name} genuinely for their time and feedback. "
                "Let them know the door is always open and we'd love to earn their business back. "
                "Let them know a team member may follow up by email with some updates. "
                "No pressure — just wish them well."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {customer_name} sincerely for taking the time to share their feedback. "
                "Let them know their insights will genuinely help us improve. "
                "Wish them all the best and let them know they're always welcome back."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound churn winback call for a canceled Stripe customer."
    )
    parser.add_argument("phone", help="Customer phone number (E.164, e.g. +15551234567)")
    parser.add_argument("--customer-id", required=True, help="Stripe customer ID (cus_...)")
    parser.add_argument("--name", required=True, help="Customer's full name")
    args = parser.parse_args()

    logging.info(
        "Initiating churn winback call to %s (%s) for customer %s",
        args.name, args.phone, args.customer_id,
    )

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "customer_id": args.customer_id,
            "customer_name": args.name,
        },
    )
