import argparse
import logging
import os

import guava
import requests
from guava import logging_utils

API_LOGIN_ID = os.environ["AUTHNET_API_LOGIN_ID"]
TRANSACTION_KEY = os.environ["AUTHNET_TRANSACTION_KEY"]
BASE_URL = (
    "https://api.authorize.net/xml/v1/request.api"
    if os.environ.get("AUTHNET_ENVIRONMENT") == "production"
    else "https://apitest.authorize.net/xml/v1/request.api"
)

ACCOUNT_PORTAL_URL = "pinnaclepayments.com/account"


def authnet_credentials() -> dict:
    return {"name": API_LOGIN_ID, "transactionKey": TRANSACTION_KEY}


def api_call(payload: dict) -> dict:
    resp = requests.post(BASE_URL, json=payload, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    messages = data.get("messages", {})
    if messages.get("resultCode") == "Error":
        raise RuntimeError(
            f"Authorize.net error: {messages.get('message', [{}])[0].get('text', 'Unknown error')}"
        )
    return data


def get_subscription(subscription_id: str) -> dict:
    payload = {
        "ARBGetSubscriptionRequest": {
            "merchantAuthentication": authnet_credentials(),
            "subscriptionId": subscription_id,
        }
    }
    return api_call(payload)


def cancel_subscription(subscription_id: str) -> dict:
    payload = {
        "ARBCancelSubscriptionRequest": {
            "merchantAuthentication": authnet_credentials(),
            "subscriptionId": subscription_id,
        }
    }
    return api_call(payload)


agent = guava.Agent(
    name="Casey",
    organization="Pinnacle Payments",
    purpose=(
        "to help Pinnacle Payments customers resolve failed subscription payments "
        "and update their payment information"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    subscription_id = call.get_variable("subscription_id")

    # Pre-call: fetch subscription to confirm it's suspended and get profile info
    subscription = {}
    customer_profile_id = ""
    try:
        data = get_subscription(subscription_id)
        sub = data.get("subscription", {})
        subscription = sub
        profile = sub.get("profile", {})
        customer_profile_id = profile.get("customerProfileId", "")
        status = sub.get("status", "")
        logging.info(
            "Pre-call subscription fetch — id: %s, status: %s, profileId: %s",
            subscription_id, status, customer_profile_id,
        )
        if status != "suspended":
            logging.warning(
                "Subscription %s is '%s', not suspended. Proceeding anyway.",
                subscription_id, status,
            )
    except Exception as e:
        logging.error(
            "Failed to fetch subscription %s before call: %s", subscription_id, e
        )

    call.set_variable("subscription", subscription)
    call.set_variable("customer_profile_id", customer_profile_id)

    call.reach_person(contact_full_name=call.get_variable("customer_name"))


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    if outcome == "unavailable":
        customer_name = call.get_variable("customer_name")
        subscription_id = call.get_variable("subscription_id")
        amount = call.get_variable("amount")
        logging.info(
            "Unable to reach %s — leaving voicemail for subscription %s",
            customer_name, subscription_id,
        )
        call.hangup(
            final_instructions=(
                f"Leave a brief, professional voicemail for {customer_name} on behalf of "
                "Pinnacle Payments. Let them know you're calling because a payment of "
                f"${amount} on their subscription wasn't able to go through and their account "
                "is currently on hold. "
                f"Ask them to log in at {ACCOUNT_PORTAL_URL} to update their payment method, "
                "or call us back at their convenience. Keep it concise and non-threatening."
            )
        )
    elif outcome == "available":
        customer_name = call.get_variable("customer_name")
        subscription_id = call.get_variable("subscription_id")
        amount = call.get_variable("amount")

        call.set_task(
            "payment_recovery",
            objective=(
                f"You're calling {customer_name} about a failed payment of ${amount} "
                f"on their Pinnacle Payments subscription (ID: {subscription_id}). "
                "Let them know the situation, understand why the payment failed, "
                "and help them get their account back in good standing."
            ),
            checklist=[
                guava.Say(
                    f"Hi {customer_name}, this is Casey calling from Pinnacle Payments. "
                    f"I'm reaching out because we noticed a payment of ${amount} on your "
                    f"subscription wasn't able to go through, and your account is currently on hold. "
                    "I wanted to reach out personally to help get this resolved."
                ),
                guava.Field(
                    key="aware_of_issue",
                    field_type="multiple_choice",
                    description="Ask if they were aware of the failed payment.",
                    choices=["yes", "no"],
                    required=True,
                ),
                guava.Field(
                    key="payment_issue_cause",
                    field_type="multiple_choice",
                    description=(
                        "Ask what they think caused the payment failure. "
                        "Be empathetic — don't make them feel accused or embarrassed."
                    ),
                    choices=[
                        "card expired",
                        "card number changed",
                        "insufficient funds",
                        "bank blocked it",
                        "not sure",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="updated_payment",
                    field_type="multiple_choice",
                    description=(
                        "Ask if they've already updated their payment method, haven't yet, "
                        "or if they'd like to cancel the subscription instead."
                    ),
                    choices=[
                        "yes, I updated my card already",
                        "no, haven't updated it yet",
                        "want to cancel subscription",
                    ],
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("payment_recovery")
def on_done(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    subscription_id = call.get_variable("subscription_id")

    cause = call.get_field("payment_issue_cause") or "not sure"
    updated_payment = call.get_field("updated_payment") or ""

    logging.info(
        "Payment recovery outcome — subscriptionId: %s, cause: %s, updated: %s",
        subscription_id, cause, updated_payment,
    )

    if "cancel" in updated_payment:
        # Customer wants to cancel — call ARBCancelSubscriptionRequest
        logging.info("Customer requested cancellation of subscription %s", subscription_id)
        try:
            cancel_subscription(subscription_id)
            logging.info("Subscription %s cancelled at customer request", subscription_id)
            call.hangup(
                final_instructions=(
                    f"Let {customer_name} know their subscription has been successfully cancelled. "
                    "No further charges will be made. "
                    "Thank them for being a Pinnacle Payments customer and wish them well."
                )
            )
        except Exception as e:
            logging.error(
                "Failed to cancel subscription %s: %s", subscription_id, e
            )
            call.hangup(
                final_instructions=(
                    f"Apologize to {customer_name} — there was a technical issue processing "
                    "the cancellation. Let them know the billing team will follow up within one "
                    "business day to confirm. Thank them for their patience."
                )
            )

    elif "yes" in updated_payment:
        # Customer says they've updated their card — payment retry is automatic
        logging.info(
            "Customer reports card updated for subscription %s — advising automatic retry",
            subscription_id,
        )
        call.hangup(
            final_instructions=(
                f"Let {customer_name} know that since they've updated their payment method, "
                "Authorize.net will automatically retry the charge within the next 24 to 48 hours. "
                "Once successful, their subscription will be reactivated immediately. "
                f"They can also log in to their account at {ACCOUNT_PORTAL_URL} "
                "to check their subscription status. "
                "Thank them for taking care of it so quickly and wish them a great day."
            )
        )

    else:
        # Customer hasn't updated their card yet
        logging.info(
            "Customer has not updated payment method for subscription %s — directing to portal",
            subscription_id,
        )
        call.hangup(
            final_instructions=(
                f"Let {customer_name} know they can update their payment method by logging "
                f"into their account at {ACCOUNT_PORTAL_URL}. "
                "Once they update their card, the payment will be retried automatically "
                "and their subscription will be reactivated. "
                "Let them know we'll also send a reminder email with a direct link. "
                "Thank them for their time and wish them a great day."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description=(
            "Outbound payment recovery call for an Authorize.net customer "
            "whose subscription payment has failed."
        )
    )
    parser.add_argument("phone", help="Customer phone number in E.164 format (e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Customer's full name")
    parser.add_argument("--email", required=True, help="Customer's email address")
    parser.add_argument("--subscription-id", required=True, help="Authorize.net ARB subscription ID")
    parser.add_argument(
        "--amount", required=True, help="Failed payment amount (e.g. 49.99)"
    )
    args = parser.parse_args()

    logging.info(
        "Initiating payment recovery call to %s (%s) for subscription %s — amount: $%s",
        args.name, args.phone, args.subscription_id, args.amount,
    )

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "customer_name": args.name,
            "customer_email": args.email,
            "subscription_id": args.subscription_id,
            "amount": args.amount,
        },
    )
