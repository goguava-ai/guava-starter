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


def get_subscription(subscription_id: str, headers: dict) -> dict | None:
    resp = requests.get(
        f"{BASE_URL}/v1/billing/subscriptions/{subscription_id}",
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
        "to help Northgate Commerce customers resolve failed subscription payments"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    subscription_id = call.get_variable("subscription_id")

    subscription = None
    try:
        token = get_access_token()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        subscription = get_subscription(subscription_id, headers)
    except Exception as e:
        logging.error("Failed to load subscription %s: %s", subscription_id, e)

    call.set_variable("subscription", subscription)
    call.reach_person(contact_full_name=customer_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    customer_name = call.get_variable("customer_name")
    subscription = call.get_variable("subscription")

    if outcome == "unavailable":
        logging.info("Unable to reach %s for payment recovery.", customer_name)
        call.hangup(
            final_instructions=(
                f"Leave a brief, professional voicemail for {customer_name} from Northgate Commerce. "
                "Let them know you're calling about a payment issue on their PayPal subscription "
                "and ask them to log into PayPal to update their payment method. "
                "Keep it concise and non-threatening."
            )
        )
    elif outcome == "available":
        failed_count = 0
        last_amount = ""
        if subscription:
            billing = subscription.get("billing_info", {})
            failed_count = billing.get("failed_payments_count", 0)
            last = billing.get("last_payment", {}).get("amount", {})
            if last.get("value"):
                last_amount = f"${last['value']} {last.get('currency_code', 'USD')}"

        call.set_task(
            "handle_outcome",
            objective=(
                f"Reach {customer_name} about a failed PayPal subscription payment. "
                f"There {'have been' if failed_count > 1 else 'has been'} {failed_count or 'a'} failed "
                f"payment{'s' if failed_count != 1 else ''}{' of ' + last_amount if last_amount else ''}. "
                "Help them understand what happened and guide them to update their payment method in PayPal."
            ),
            checklist=[
                guava.Say(
                    f"Hi {customer_name}, this is Alex calling from Northgate Commerce. "
                    "I'm reaching out because we noticed a payment issue with your PayPal subscription. "
                    + (f"There {'have' if failed_count != 1 else 'has'} been {failed_count} failed "
                       f"payment attempt{'s' if failed_count != 1 else ''}" if failed_count else "A recent payment didn't go through")
                    + ". I wanted to reach out to help get this sorted quickly."
                ),
                guava.Field(
                    key="aware",
                    field_type="multiple_choice",
                    description="Ask if they were aware of the payment issue.",
                    choices=["yes", "no"],
                    required=True,
                ),
                guava.Field(
                    key="cause",
                    field_type="multiple_choice",
                    description="Ask what they think caused the payment failure.",
                    choices=["card expired", "insufficient funds", "PayPal account issue", "not sure"],
                    required=True,
                ),
                guava.Field(
                    key="willing_to_update",
                    field_type="multiple_choice",
                    description=(
                        "Ask if they're willing to log into PayPal and update their payment method "
                        "to prevent future failures."
                    ),
                    choices=["yes, I'll update it", "already updated", "need help", "want to cancel"],
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("handle_outcome")
def on_done(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    subscription_id = call.get_variable("subscription_id")
    cause = call.get_field("cause") or ""
    willing = call.get_field("willing_to_update") or ""

    logging.info(
        "Payment recovery outcome for subscription %s — cause: %s, response: %s",
        subscription_id, cause, willing,
    )

    if "cancel" in willing:
        call.hangup(
            final_instructions=(
                f"Acknowledge {customer_name}'s wish to cancel. Let them know they can "
                "cancel their subscription by logging into PayPal and going to their subscription settings. "
                "Thank them for being a customer and wish them well."
            )
        )
    elif "already updated" in willing:
        call.hangup(
            final_instructions=(
                f"Let {customer_name} know PayPal will automatically retry the payment "
                "with the updated method. They should see the charge go through within 24 hours. "
                "Thank them for updating quickly and wish them a great day."
            )
        )
    elif "help" in willing:
        call.hangup(
            final_instructions=(
                f"Guide {customer_name} to update their payment method: "
                "log into paypal.com → click the gear icon → Payments → Manage automatic payments → "
                "find Northgate Commerce → Update payment method. "
                "Let them know PayPal will retry once updated. Thank them for their time."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {customer_name} for their time. Let them know they need to update "
                "their payment method in PayPal to avoid subscription interruption. "
                "PayPal will retry automatically once the method is updated. "
                "Wish them a great day."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound PayPal subscription payment recovery call."
    )
    parser.add_argument("phone", help="Customer phone number (E.164)")
    parser.add_argument("--name", required=True, help="Customer's full name")
    parser.add_argument("--subscription-id", required=True, help="PayPal subscription ID (I-...)")
    args = parser.parse_args()

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "customer_name": args.name,
            "subscription_id": args.subscription_id,
        },
    )
