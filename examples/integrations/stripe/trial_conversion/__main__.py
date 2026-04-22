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


def get_customer(customer_id: str) -> dict | None:
    resp = requests.get(f"{BASE_URL}/v1/customers/{customer_id}", auth=AUTH, timeout=10)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def list_trialing_subscriptions(customer_id: str) -> list:
    resp = requests.get(
        f"{BASE_URL}/v1/subscriptions",
        auth=AUTH,
        params={"customer": customer_id, "status": "trialing", "limit": 3},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("data", [])


def convert_trial_to_paid(sub_id: str) -> dict:
    """Ends the trial immediately, converting the subscription to paid billing now."""
    resp = requests.post(
        f"{BASE_URL}/v1/subscriptions/{sub_id}",
        auth=AUTH,
        data={"trial_end": "now"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def extend_trial(sub_id: str, new_trial_end_unix: int) -> dict:
    """Extends the trial end date by updating trial_end."""
    resp = requests.post(
        f"{BASE_URL}/v1/subscriptions/{sub_id}",
        auth=AUTH,
        data={"trial_end": str(new_trial_end_unix)},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


agent = guava.Agent(
    name="Jordan",
    organization="Luminary",
    purpose=(
        "to check in with Luminary trial users nearing the end of their trial "
        "and help them decide whether to convert to a paid plan"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    customer_id = call.get_variable("customer_id")
    customer_name = call.get_variable("customer_name")

    sub_id = None
    plan_name = "Luminary"
    trial_end_date = ""
    days_remaining = 0
    billing_amount_str = ""

    try:
        subscriptions = list_trialing_subscriptions(customer_id)
        if subscriptions:
            sub = subscriptions[0]
            sub_id = sub["id"]

            trial_end = sub.get("trial_end")
            if trial_end:
                trial_dt = datetime.utcfromtimestamp(trial_end)
                trial_end_date = trial_dt.strftime("%B %d, %Y")
                days_remaining = max(0, (trial_dt - datetime.now(timezone.utc)).days)

            items = sub.get("items", {}).get("data", [])
            if items:
                price = items[0].get("price", {})
                plan_name = price.get("nickname") or "Luminary"
                unit_amount = price.get("unit_amount")
                currency = price.get("currency", "usd")
                interval = price.get("recurring", {}).get("interval", "month")
                if unit_amount is not None:
                    billing_amount_str = (
                        f"${unit_amount / 100:,.2f} {currency.upper()}/{interval}"
                    )
    except Exception as e:
        logging.error("Failed to fetch trial subscription for %s: %s", customer_id, e)

    call.sub_id = sub_id
    call.plan_name = plan_name
    call.trial_end_date = trial_end_date
    call.days_remaining = days_remaining
    call.billing_amount_str = billing_amount_str

    call.reach_person(contact_full_name=customer_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    customer_name = call.get_variable("customer_name")

    if outcome == "unavailable":
        logging.info("Unable to reach %s for trial conversion call", customer_name)
        call.hangup(
            final_instructions=(
                f"Leave a brief voicemail for {customer_name} on behalf of Luminary. "
                f"Let them know their trial ends on {call.trial_end_date or 'soon'} and you wanted "
                "to check in before then. Let them know we'll send an email as well. "
                "Keep it brief, warm, and low-pressure."
            )
        )
    elif outcome == "available":
        if not call.sub_id:
            logging.info("No trialing subscription found for customer %s", call.get_variable("customer_id"))
            call.hangup(
                final_instructions=(
                    f"Let {customer_name} know you're calling from Luminary about their trial. "
                    "Mention that it looks like their trial may have already ended or converted. "
                    "Offer to have a specialist follow up by email if they have questions. "
                    "Be warm and apologetic for any confusion."
                )
            )
            return

        days_note = (
            f"just {call.days_remaining} day{'s' if call.days_remaining != 1 else ''}"
            if call.days_remaining > 0
            else "very soon"
        )
        billing_note = f" at {call.billing_amount_str}" if call.billing_amount_str else ""

        call.set_task(
            "handle_decision",
            objective=(
                f"Check in with {customer_name} about their Luminary trial, which ends "
                f"on {call.trial_end_date} ({days_note} away). "
                "Understand how the trial went, answer questions, and convert them to paid if ready."
            ),
            checklist=[
                guava.Say(
                    f"Hi {customer_name}, this is Jordan calling from Luminary. "
                    f"I'm reaching out because your trial is coming to an end on {call.trial_end_date} "
                    f"— just {days_note} away. I wanted to check in personally and see how "
                    "things are going."
                ),
                guava.Field(
                    key="trial_experience",
                    field_type="multiple_choice",
                    description="Ask how their trial experience has been overall.",
                    choices=["excellent", "good", "okay", "not great"],
                    required=True,
                ),
                guava.Field(
                    key="primary_use_case",
                    field_type="text",
                    description=(
                        "Ask what they've been primarily using Luminary for during the trial. "
                        "This helps us make sure they're set up for success."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="questions",
                    field_type="text",
                    description=(
                        "Ask if they have any questions before making a decision. "
                        "Capture any questions or concerns they raise."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="ready_to_convert",
                    field_type="multiple_choice",
                    description=(
                        f"Ask if they're ready to continue with a paid plan{billing_note} "
                        "when their trial ends, or if they'd like more time or have concerns."
                    ),
                    choices=[
                        "yes/convert now",
                        "yes/happy to convert at trial end",
                        "need more time/please extend trial",
                        "not interested/will cancel",
                    ],
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("handle_decision")
def handle_decision(call: guava.Call) -> None:
    customer_id = call.get_variable("customer_id")
    customer_name = call.get_variable("customer_name")
    experience = call.get_field("trial_experience") or "unknown"
    questions = call.get_field("questions") or ""
    decision = call.get_field("ready_to_convert") or ""

    logging.info(
        "Trial conversion decision for %s: experience=%s, decision=%s",
        customer_id, experience, decision,
    )

    if "convert now" in decision:
        if not call.sub_id:
            call.hangup(
                final_instructions=(
                    "Apologize for a technical issue and let them know a specialist "
                    "will process their conversion and confirm by email today."
                )
            )
            return
        try:
            convert_trial_to_paid(call.sub_id)
            logging.info("Trial converted to paid for subscription %s", call.sub_id)
            call.hangup(
                final_instructions=(
                    f"Congratulate {customer_name} and let them know their subscription "
                    f"is now active — the trial has been converted to a paid plan. "
                    + (f"They'll be billed {call.billing_amount_str} starting today. " if call.billing_amount_str else "")
                    + "Thank them enthusiastically for choosing Luminary. "
                    "Let them know our team is always here if they need help getting the most "
                    "out of the product. Wish them a great day."
                )
            )
        except Exception as e:
            logging.error("Failed to convert trial for sub %s: %s", call.sub_id, e)
            call.hangup(
                final_instructions=(
                    "Apologize for a technical issue and let them know their conversion "
                    "request has been noted — a specialist will process it and confirm by email."
                )
            )

    elif "trial end" in decision:
        call.hangup(
            final_instructions=(
                f"Thank {customer_name} for their enthusiasm. "
                f"Let them know their subscription will automatically activate on {call.trial_end_date} "
                + (f"and they'll be billed {call.billing_amount_str} at that time. " if call.billing_amount_str else ". ")
                + "Let them know they'll receive a confirmation email. "
                "Thank them for choosing Luminary and wish them a great day."
            )
        )

    elif "extend" in decision:
        # Extend by 7 days
        import time
        current_trial_end = int(time.time()) + (call.days_remaining * 86400)
        new_trial_end = current_trial_end + (7 * 86400)
        try:
            if call.sub_id:
                extend_trial(call.sub_id, new_trial_end)
                new_end_date = datetime.utcfromtimestamp(new_trial_end).strftime("%B %d, %Y")
                logging.info("Trial extended for sub %s to %s", call.sub_id, new_end_date)
                call.hangup(
                    final_instructions=(
                        f"Let {customer_name} know their trial has been extended by 7 days "
                        f"to {new_end_date}. "
                        "Let them know we'd love to hear how we can make the most of that time "
                        "and that our team is available if they have questions. "
                        "Thank them warmly."
                    )
                )
            else:
                raise ValueError("No subscription ID available")
        except Exception as e:
            logging.error("Failed to extend trial: %s", e)
            call.hangup(
                final_instructions=(
                    "Apologize for a technical issue. Let them know their extension request "
                    "has been noted and a specialist will apply it and confirm by email today."
                )
            )

    else:  # not interested
        call.hangup(
            final_instructions=(
                f"Thank {customer_name} for giving Luminary a try. "
                "Let them know their trial will end on the scheduled date with no charge. "
                + (
                    "Let them know their feedback has been passed along to our product team. "
                    if questions
                    else ""
                )
                + "Wish them all the best and let them know we hope to earn their business in the future."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound trial conversion call for a Stripe customer in a trialing subscription."
    )
    parser.add_argument("phone", help="Customer phone number (E.164, e.g. +15551234567)")
    parser.add_argument("--customer-id", required=True, help="Stripe customer ID (cus_...)")
    parser.add_argument("--name", required=True, help="Customer's full name")
    args = parser.parse_args()

    logging.info(
        "Initiating trial conversion call to %s (%s) for customer %s",
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
