import guava
import os
import logging
from guava import logging_utils
import argparse
import requests


API_LOGIN_ID = os.environ["AUTHORIZENET_API_LOGIN_ID"]
TRANSACTION_KEY = os.environ["AUTHORIZENET_TRANSACTION_KEY"]
# Sandbox: https://apitest.authorize.net/xml/v1/request.api
# Production: https://api.authorize.net/xml/v1/request.api
BASE_URL = "https://apitest.authorize.net/xml/v1/request.api"


def auth_block():
    return {
        "name": API_LOGIN_ID,
        "transactionKey": TRANSACTION_KEY,
    }


def get_customer_profile(customer_profile_id: str):
    payload = {
        "getCustomerProfileRequest": {
            "merchantAuthentication": auth_block(),
            "customerProfileId": customer_profile_id,
            "includeIssuerInfo": "true",
        }
    }
    resp = requests.post(BASE_URL, json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()


def charge_customer_profile(
    customer_profile_id: str,
    customer_payment_profile_id: str,
    amount: str,
):
    payload = {
        "createTransactionRequest": {
            "merchantAuthentication": auth_block(),
            "transactionRequest": {
                "transactionType": "authCaptureTransaction",
                "amount": amount,
                "profile": {
                    "customerProfileId": customer_profile_id,
                    "paymentProfile": {
                        "paymentProfileId": customer_payment_profile_id,
                    },
                },
            },
        }
    }
    resp = requests.post(BASE_URL, json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()


def fetch_customer_data(customer_profile_id: str):
    return get_customer_profile(customer_profile_id)


agent = guava.Agent(
    name="Jordan",
    organization="Harbor Health Services",
    purpose="to collect an outstanding balance on a patient account",
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    customer_profile_id = call.get_variable("customer_profile_id")

    try:
        profile_data = fetch_customer_data(customer_profile_id)
    except Exception as e:
        logging.error("Pre-fetch of customer profile failed: %s", e)
        profile_data = None

    payment_profile_id = None
    card_last_four = None
    if profile_data:
        try:
            profiles = (
                profile_data.get("profile", {})
                .get("paymentProfiles", [])
            )
            if profiles:
                first_profile = profiles[0]
                payment_profile_id = first_profile.get("customerPaymentProfileId")
                credit_card = first_profile.get("payment", {}).get("creditCard", {})
                card_last_four = credit_card.get("cardNumber", "card on file")
        except Exception as e:
            logging.error("Error extracting payment profile: %s", e)

    call.set_variable("profile_data", profile_data)
    call.set_variable("payment_profile_id", payment_profile_id)
    call.set_variable("card_last_four", card_last_four)

    call.reach_person(contact_full_name=call.get_variable("customer_name"))


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    if outcome == "unavailable":
        customer_name = call.get_variable("customer_name")
        outstanding_balance = call.get_variable("outstanding_balance")
        call.hangup(
            final_instructions=(
                f"Leave a brief, professional voicemail for {customer_name}. "
                f"State that this is Jordan calling from Harbor Health Services regarding an "
                f"outstanding balance of ${outstanding_balance} on their account. "
                f"Ask them to call our billing office at (555) 882-4400 at their earliest "
                f"convenience. Office hours are Monday through Friday 8am to 5pm. "
                f"Be professional and courteous."
            )
        )
    elif outcome == "available":
        customer_name = call.get_variable("customer_name")
        outstanding_balance = call.get_variable("outstanding_balance")
        card_last_four = call.get_variable("card_last_four")
        card_description = (
            f"ending in {card_last_four}" if card_last_four else "on file"
        )

        call.set_task(
            "collect_balance",
            objective=(
                f"Collect an outstanding balance of ${outstanding_balance} from {customer_name}. "
                f"Confirm the amount owed, ask how they would like to pay, and process the payment "
                f"against their stored payment profile if they choose to pay by card on file."
            ),
            checklist=[
                guava.Say(
                    f"Hi, may I please speak with {customer_name}? "
                    f"This is Jordan calling from Harbor Health Services billing."
                ),
                guava.Say(
                    f"Thank you, {customer_name}. I'm calling about an outstanding balance "
                    f"of ${outstanding_balance} on your account. I'd like to help you take "
                    f"care of this today if possible."
                ),
                guava.Field(
                    key="balance_confirmed",
                    field_type="multiple_choice",
                    description=(
                        f"Ask the caller if they are aware of the outstanding balance of "
                        f"${outstanding_balance} and if the amount sounds correct to them."
                    ),
                    choices=["yes, confirmed", "no, I have questions", "I already paid this"],
                    required=True,
                ),
                guava.Field(
                    key="payment_method",
                    field_type="multiple_choice",
                    description=(
                        f"Ask the caller how they would like to pay the balance of ${outstanding_balance}. "
                        f"If they have a card on file ({card_description}), offer to charge that card now. "
                        f"Also offer to take a new card number, or let them know they can mail a check."
                    ),
                    choices=["charge card on file", "use a new card", "will mail a check", "need more time"],
                    required=True,
                ),
                guava.Field(
                    key="payment_amount",
                    field_type="multiple_choice",
                    description=(
                        f"Ask if they would like to pay the full balance of ${outstanding_balance} "
                        f"today or a partial amount."
                    ),
                    choices=["full balance", "partial payment"],
                    required=True,
                ),
                guava.Field(
                    key="partial_amount",
                    field_type="text",
                    description=(
                        "If paying a partial amount, ask how much they would like to pay today. "
                        "Only collect this field if they selected partial payment."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="confirm_payment",
                    field_type="multiple_choice",
                    description=(
                        "Confirm the payment details with the caller before processing: the amount "
                        "and the payment method. Ask them to confirm they are ready to proceed."
                    ),
                    choices=["yes, proceed", "no, cancel"],
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("collect_balance")
def on_done(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    outstanding_balance = call.get_variable("outstanding_balance")
    customer_profile_id = call.get_variable("customer_profile_id")
    payment_profile_id = call.get_variable("payment_profile_id")

    balance_confirmed = call.get_field("balance_confirmed")
    payment_method = call.get_field("payment_method")
    confirm_payment = call.get_field("confirm_payment")
    payment_amount_choice = call.get_field("payment_amount")
    partial_amount_str = call.get_field("partial_amount")

    if balance_confirmed == "I already paid this":
        call.hangup(
            final_instructions=(
                f"Apologize to {customer_name} for the confusion and let them know you'll "
                f"flag their account for review by our billing team, who will follow up within 2 "
                f"business days. Thank them for their time and patience. Be warm and professional."
            )
        )
        return

    if balance_confirmed == "no, I have questions":
        call.hangup(
            final_instructions=(
                f"Thank {customer_name} for letting you know. Give them the billing office "
                f"number (555) 882-4400 so they can speak with a billing specialist who can review "
                f"the charges in detail. Offer office hours as Monday through Friday 8am to 5pm. "
                f"Be friendly and professional."
            )
        )
        return

    if confirm_payment != "yes, proceed":
        call.hangup(
            final_instructions=(
                f"Let {customer_name} know that no payment has been processed today. "
                f"Let them know they can call back at (555) 882-4400 when they are ready. "
                f"Be friendly and professional."
            )
        )
        return

    if payment_method in ("use a new card", "will mail a check", "need more time"):
        call.hangup(
            final_instructions=(
                f"Thank {customer_name} for their time. "
                f"If they are mailing a check, give them the mailing address: "
                f"Harbor Health Services, PO Box 1850, Portland OR 97201. "
                f"If they want to use a new card or need more time, give them the billing office "
                f"number (555) 882-4400 and let them know the team is available Monday through "
                f"Friday 8am to 5pm. Be warm and professional."
            )
        )
        return

    # Charge card on file
    if not payment_profile_id:
        call.hangup(
            final_instructions=(
                f"Apologize to {customer_name} and let them know we were unable to locate "
                f"their card on file. Ask them to call our billing office at (555) 882-4400 "
                f"to provide a payment method directly. Be apologetic and professional."
            )
        )
        return

    try:
        if payment_amount_choice == "partial payment" and partial_amount_str:
            charge_amount = f"{float(partial_amount_str.replace('$', '').replace(',', '')):.2f}"
        else:
            charge_amount = f"{float(outstanding_balance.replace('$', '').replace(',', '')):.2f}"
    except ValueError as e:
        logging.error("Amount parsing error: %s", e)
        call.hangup(
            final_instructions=(
                f"Apologize to {customer_name} and let them know there was a problem "
                f"processing the payment amount. Ask them to call (555) 882-4400 to complete "
                f"the payment. Be apologetic and professional."
            )
        )
        return

    charge_result = None
    error_message = None
    try:
        charge_result = charge_customer_profile(
            customer_profile_id=customer_profile_id,
            customer_payment_profile_id=payment_profile_id,
            amount=charge_amount,
        )
        result_code = charge_result.get("messages", {}).get("resultCode", "Error")
        if result_code != "Ok":
            trans_response = charge_result.get("transactionResponse", {})
            errors = trans_response.get("errors", [])
            if errors:
                error_message = errors[0].get("errorText", "payment was declined")
            else:
                error_message = "payment could not be processed"
    except Exception as e:
        logging.error("Authorize.net API error during balance collection: %s", e)
        error_message = "a system error occurred"

    if error_message:
        call.hangup(
            final_instructions=(
                f"Tell {customer_name} that unfortunately the payment of ${charge_amount} "
                f"was not successful because {error_message}. Apologize and provide the billing "
                f"office number (555) 882-4400 so they can resolve this directly. "
                f"Be empathetic and professional."
            )
        )
    else:
        trans_id = (charge_result or {}).get("transactionResponse", {}).get("transId", "N/A")
        remaining = ""
        try:
            original = float(outstanding_balance.replace("$", "").replace(",", ""))
            charged = float(charge_amount)
            if charged < original:
                remaining = f" The remaining balance of ${original - charged:.2f} will be due on your next statement."
        except ValueError:
            pass

        call.hangup(
            final_instructions=(
                f"Tell {customer_name} that their payment of ${charge_amount} has been "
                f"successfully processed. Their confirmation number is {trans_id}.{remaining} "
                f"A receipt will be sent to the email address on their account. "
                f"Thank them warmly for taking care of this and wish them good health. "
                f"Be warm and professional."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Call a patient to collect an outstanding balance."
    )
    parser.add_argument("phone", help="Patient phone number in E.164 format (e.g. +15551234567)")
    parser.add_argument("--customer-profile-id", required=True, help="Authorize.net customer profile ID")
    parser.add_argument("--name", required=True, help="Patient full name")
    parser.add_argument("--balance", required=True, help="Outstanding balance amount (e.g. 350.00)")
    args = parser.parse_args()

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "customer_name": args.name,
            "customer_profile_id": args.customer_profile_id,
            "outstanding_balance": args.balance,
        },
    )
