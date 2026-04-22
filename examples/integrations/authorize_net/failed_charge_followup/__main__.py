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
                "transactionSettings": {
                    "setting": [
                        {
                            "settingName": "recurringBilling",
                            "settingValue": "true",
                        }
                    ]
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
    name="Maya",
    organization="Crestview Dental",
    purpose="to follow up with patients about a declined payment and offer assistance",
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
    if profile_data:
        try:
            profiles = (
                profile_data.get("profile", {})
                .get("paymentProfiles", [])
            )
            if profiles:
                payment_profile_id = profiles[0].get("customerPaymentProfileId")
        except Exception as e:
            logging.error("Error extracting payment profile ID: %s", e)

    call.set_variable("payment_profile_id", payment_profile_id)

    call.reach_person(contact_full_name=call.get_variable("customer_name"))


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    if outcome == "unavailable":
        customer_name = call.get_variable("customer_name")
        failed_amount = call.get_variable("failed_amount")
        call.hangup(
            final_instructions=(
                f"Leave a brief, professional voicemail for {customer_name}. "
                f"State that this is Maya calling from Crestview Dental billing regarding a declined "
                f"payment of ${failed_amount} on their account. Ask them to call us back at "
                f"(555) 410-2200 at their earliest convenience to resolve this. Do not mention "
                f"any sensitive financial details beyond the amount. Be professional and courteous."
            )
        )
    elif outcome == "available":
        customer_name = call.get_variable("customer_name")
        failed_amount = call.get_variable("failed_amount")

        call.set_task(
            "failed_charge_followup",
            objective=(
                f"Reach {customer_name} to follow up about a declined charge of "
                f"${failed_amount} and offer to retry the payment or update their payment method."
            ),
            checklist=[
                guava.Say(
                    f"Hi, may I please speak with {customer_name}? "
                    f"This is Maya calling from Crestview Dental billing."
                ),
                guava.Say(
                    f"Thank you for taking my call, {customer_name}. I'm reaching out because "
                    f"a recent payment of ${failed_amount} for your account was declined. "
                    f"I'd like to help you get this resolved quickly."
                ),
                guava.Field(
                    key="aware_of_issue",
                    field_type="multiple_choice",
                    description=(
                        "Ask if the customer was aware that their payment was declined and if they "
                        "know the reason, such as insufficient funds, expired card, or incorrect details."
                    ),
                    choices=["yes, aware", "no, not aware", "card expired", "other issue"],
                    required=True,
                ),
                guava.Field(
                    key="resolution_choice",
                    field_type="multiple_choice",
                    description=(
                        f"Ask the customer how they would like to resolve the declined payment of "
                        f"${failed_amount}. Offer to retry the charge on their card on file now, "
                        f"or let them know they can update their payment method by calling the office. "
                        f"If they've already updated their card on file, offer to retry the charge now."
                    ),
                    choices=["retry charge now", "will update payment method", "call office to resolve"],
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("failed_charge_followup")
def on_done(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    failed_amount = call.get_variable("failed_amount")
    customer_profile_id = call.get_variable("customer_profile_id")
    payment_profile_id = call.get_variable("payment_profile_id")

    resolution = call.get_field("resolution_choice")

    if resolution == "retry charge now":
        if not payment_profile_id:
            call.hangup(
                final_instructions=(
                    f"Apologize to {customer_name} and let them know we were unable to locate "
                    f"their payment profile on file. Ask them to call our billing office at their "
                    f"earliest convenience so we can update their information and process the payment. "
                    f"Be apologetic and professional."
                )
            )
            return

        charge_result = None
        error_message = None
        try:
            charge_result = charge_customer_profile(
                customer_profile_id=customer_profile_id,
                customer_payment_profile_id=payment_profile_id,
                amount=failed_amount,
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
            logging.error("Authorize.net API error during charge retry: %s", e)
            error_message = "a system error occurred"

        if error_message:
            call.hangup(
                final_instructions=(
                    f"Tell {customer_name} that unfortunately the charge of ${failed_amount} "
                    f"was not successful because {error_message}. Apologize and let them know they "
                    f"should contact our billing office to update their payment information. "
                    f"Provide the office number as (555) 410-2200. Be empathetic and professional."
                )
            )
        else:
            trans_id = (charge_result or {}).get("transactionResponse", {}).get("transId", "N/A")
            call.hangup(
                final_instructions=(
                    f"Tell {customer_name} that their payment of ${failed_amount} was "
                    f"successfully processed and their confirmation number is {trans_id}. "
                    f"Thank them for resolving this promptly and wish them a great day. "
                    f"Be warm and professional."
                )
            )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {customer_name} for their time. Let them know that if they need to "
                f"update their payment method they can call our billing office at (555) 410-2200 "
                f"or visit our website. Remind them the outstanding balance is ${failed_amount}. "
                f"Be friendly and professional."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Call a patient to follow up on a failed charge."
    )
    parser.add_argument("phone", help="Patient phone number in E.164 format (e.g. +15551234567)")
    parser.add_argument("--customer-profile-id", required=True, help="Authorize.net customer profile ID")
    parser.add_argument("--name", required=True, help="Patient full name")
    parser.add_argument("--amount", required=True, help="Failed charge amount (e.g. 125.00)")
    args = parser.parse_args()

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "customer_name": args.name,
            "customer_profile_id": args.customer_profile_id,
            "failed_amount": args.amount,
        },
    )
