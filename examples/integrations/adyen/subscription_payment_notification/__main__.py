import guava
import os
import logging
from guava import logging_utils
import argparse
import requests


ADYEN_API_KEY = os.environ["ADYEN_API_KEY"]
ADYEN_MERCHANT_ACCOUNT = os.environ["ADYEN_MERCHANT_ACCOUNT"]
RECURRING_BASE_URL = "https://pal-test.adyen.com/pal/servlet/Recurring/v68"

HEADERS = {
    "X-API-Key": ADYEN_API_KEY,
    "Content-Type": "application/json",
}


def fetch_recurring_details(shopper_reference: str) -> dict:
    """Fetch stored recurring payment details for a shopper."""
    resp = requests.post(
        f"{RECURRING_BASE_URL}/listRecurringDetails",
        headers=HEADERS,
        json={
            "merchantAccount": ADYEN_MERCHANT_ACCOUNT,
            "shopperReference": shopper_reference,
            "recurring": {
                "contract": "RECURRING",
            },
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


agent = guava.Agent(
    name="Sophie",
    organization="Meridian Retail",
    purpose="to notify customers about an upcoming subscription charge and answer their questions",
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(contact_full_name=call.get_variable("customer_name"))


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    customer_name = call.get_variable("customer_name")
    shopper_reference = call.get_variable("shopper_reference")
    plan_name = call.get_variable("plan_name")
    charge_amount = call.get_variable("charge_amount")
    currency = call.get_variable("currency")
    charge_date = call.get_variable("charge_date")

    if outcome == "unavailable":
        call.hangup(
            final_instructions=(
                f"Leave a brief, professional voicemail for {customer_name}. "
                f"Mention that this is Sophie from Meridian Retail calling about their upcoming "
                f"{plan_name} subscription renewal of {charge_amount} {currency} "
                f"scheduled for {charge_date}. Ask them to visit meridianretail.com/account "
                "or call 1-800-555-0147 if they have any questions or wish to make changes. "
                "Keep the message friendly and under 30 seconds."
            )
        )
    elif outcome == "available":
        payment_summary = "payment method on file"
        try:
            details = fetch_recurring_details(shopper_reference)
            stored = details.get("details", [])
            if stored:
                first = stored[0].get("RecurringDetail", {})
                card = first.get("card", {})
                last_four = card.get("number", "")
                payment_summary = f"card ending in {last_four}" if last_four else "payment method on file"
            logging.info(
                "Fetched recurring details for shopper %s: %s",
                shopper_reference,
                payment_summary,
            )
        except Exception as e:
            logging.error("Could not fetch recurring details for %s: %s", shopper_reference, e)

        call.set_task(
            "subscription_notification",
            objective=(
                f"Notify {customer_name} of an upcoming {plan_name} subscription charge of "
                f"{charge_amount} {currency} on {charge_date}. Confirm they are aware, "
                "answer any questions about their plan, and capture whether they want to make any changes."
            ),
            checklist=[
                guava.Say(
                    f"Hi {customer_name}, this is Sophie calling from Meridian Retail. "
                    f"I'm reaching out with a quick heads-up about your upcoming {plan_name} subscription renewal."
                ),
                guava.Field(
                    key="aware_of_charge",
                    field_type="multiple_choice",
                    description=(
                        f"Inform {customer_name} that a charge of {charge_amount} {currency} "
                        f"for their {plan_name} plan is scheduled to process on {charge_date} "
                        f"using their {payment_summary}. Ask if they were aware of this upcoming charge."
                    ),
                    choices=["yes", "no"],
                    required=True,
                ),
                guava.Field(
                    key="has_questions",
                    field_type="multiple_choice",
                    description=(
                        f"Ask {customer_name} if they have any questions about their {plan_name} "
                        "plan, what it includes, or the billing amount."
                    ),
                    choices=["yes", "no"],
                    required=True,
                ),
                guava.Field(
                    key="desired_action",
                    field_type="multiple_choice",
                    description=(
                        f"Ask {customer_name} if they would like to make any changes before the charge "
                        f"processes on {charge_date}."
                    ),
                    choices=[
                        "no changes, proceed as scheduled",
                        "I want to update my payment method",
                        "I want to upgrade or downgrade my plan",
                        "I want to cancel before the renewal",
                    ],
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("subscription_notification")
def handle_outcome(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    shopper_reference = call.get_variable("shopper_reference")
    plan_name = call.get_variable("plan_name")
    charge_amount = call.get_variable("charge_amount")
    currency = call.get_variable("currency")
    charge_date = call.get_variable("charge_date")

    aware = call.get_field("aware_of_charge")
    has_questions = call.get_field("has_questions")
    action = call.get_field("desired_action")

    logging.info(
        "Subscription notification outcome for %s (shopper: %s): aware=%s, questions=%s, action=%s",
        customer_name,
        shopper_reference,
        aware,
        has_questions,
        action,
    )

    if action == "no changes, proceed as scheduled":
        call.hangup(
            final_instructions=(
                f"Thank {customer_name} for confirming. Let them know their {plan_name} "
                f"subscription will renew on {charge_date} as planned, and they will receive an "
                "email receipt once the payment processes. Wish them a great day and thank them "
                "for being a valued Meridian Retail customer."
            )
        )
    elif action == "I want to update my payment method":
        call.hangup(
            final_instructions=(
                f"Let {customer_name} know they can update their payment method at any time by "
                "visiting meridianretail.com/account/billing and signing in. Changes made before "
                f"{charge_date} will apply to this renewal. Offer our support line at "
                "1-800-555-0147 if they need assistance. Thank them."
            )
        )
    elif action == "I want to upgrade or downgrade my plan":
        call.hangup(
            final_instructions=(
                f"Tell {customer_name} that plan changes can be made at meridianretail.com/account/plan. "
                "If they change their plan before the renewal date, the new pricing will apply to this billing cycle. "
                "Let them know our team is also available at 1-800-555-0147 to walk them through options. "
                "Thank them for reaching out."
            )
        )
    elif action == "I want to cancel before the renewal":
        call.hangup(
            final_instructions=(
                f"Acknowledge {customer_name}'s request to cancel before the renewal on {charge_date}. "
                "Let them know they can cancel at meridianretail.com/account/cancel, or they can speak with our "
                "retention team at 1-800-555-0147 who may be able to offer a pause or discount. "
                "Assure them that if they cancel before the renewal date, they will not be charged. "
                "Thank them for being a Meridian Retail customer."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {customer_name} for their time. Let them know our team is always available "
                "at meridianretail.com/support or 1-800-555-0147 if they have any questions. "
                "Wish them a great day."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Proactively notify a customer about an upcoming subscription renewal charge."
    )
    parser.add_argument("phone", help="Customer phone number in E.164 format (e.g. +12125550100)")
    parser.add_argument("--name", required=True, help="Customer full name")
    parser.add_argument("--shopper-reference", required=True, help="Adyen shopper reference ID")
    parser.add_argument("--plan", required=True, help="Subscription plan name (e.g. 'Pro Annual')")
    parser.add_argument("--amount", required=True, help="Upcoming charge amount (e.g. 299.00)")
    parser.add_argument("--currency", default="USD", help="Currency code (default: USD)")
    parser.add_argument("--charge-date", required=True, help="Charge date (e.g. 'April 15th')")
    args = parser.parse_args()

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "customer_name": args.name,
            "shopper_reference": args.shopper_reference,
            "plan_name": args.plan,
            "charge_amount": args.amount,
            "currency": args.currency,
            "charge_date": args.charge_date,
        },
    )
