import guava
import os
import logging
from guava import logging_utils
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


def create_customer_profile(
    first_name: str,
    last_name: str,
    email: str,
    phone: str,
    card_number: str,
    exp_date: str,
    card_code: str,
    address: str,
    city: str,
    state: str,
    zip_code: str,
):
    payload = {
        "createCustomerProfileRequest": {
            "merchantAuthentication": auth_block(),
            "profile": {
                "merchantCustomerId": f"{first_name.lower()}.{last_name.lower()}",
                "email": email,
                "paymentProfiles": [
                    {
                        "customerType": "individual",
                        "billTo": {
                            "firstName": first_name,
                            "lastName": last_name,
                            "address": address,
                            "city": city,
                            "state": state,
                            "zip": zip_code,
                            "phoneNumber": phone,
                        },
                        "payment": {
                            "creditCard": {
                                "cardNumber": card_number,
                                "expirationDate": exp_date,
                                "cardCode": card_code,
                            }
                        },
                    }
                ],
            },
        }
    }
    resp = requests.post(BASE_URL, json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()


def create_subscription(
    customer_profile_id: str,
    payment_profile_id: str,
    first_name: str,
    last_name: str,
    monthly_amount: str,
    total_occurrences: int,
    start_date: str,
):
    payload = {
        "ARBCreateSubscriptionRequest": {
            "merchantAuthentication": auth_block(),
            "subscription": {
                "name": f"Payment Plan - {first_name} {last_name}",
                "paymentSchedule": {
                    "interval": {
                        "length": "1",
                        "unit": "months",
                    },
                    "startDate": start_date,
                    "totalOccurrences": str(total_occurrences),
                    "trialOccurrences": "0",
                },
                "amount": monthly_amount,
                "trialAmount": "0.00",
                "profile": {
                    "customerProfileId": customer_profile_id,
                    "customerPaymentProfileId": payment_profile_id,
                },
            },
        }
    }
    resp = requests.post(BASE_URL, json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()


agent = guava.Agent(
    name="Jordan",
    organization="Harbor Health Services",
    purpose="to help patients enroll in a payment plan for their outstanding balance",
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "payment_plan_enrollment",
        objective=(
            "Guide the patient through enrolling in a monthly payment plan for their outstanding balance. "
            "Collect their personal information, payment details, and preferred monthly payment amount."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Harbor Health Services billing department. "
                "My name is Jordan and I can help you set up a payment plan today. "
                "This will only take a few minutes."
            ),
            guava.Field(
                key="first_name",
                field_type="text",
                description="Ask for the caller's first name.",
                required=True,
            ),
            guava.Field(
                key="last_name",
                field_type="text",
                description="Ask for the caller's last name.",
                required=True,
            ),
            guava.Field(
                key="email",
                field_type="text",
                description="Ask for the caller's email address for billing confirmation emails.",
                required=True,
            ),
            guava.Field(
                key="phone",
                field_type="text",
                description="Ask for the caller's phone number.",
                required=True,
            ),
            guava.Field(
                key="total_balance",
                field_type="text",
                description=(
                    "Ask the caller what their total outstanding balance is. "
                    "They can find this on their statement. Collect the dollar amount."
                ),
                required=True,
            ),
            guava.Field(
                key="monthly_payment",
                field_type="text",
                description=(
                    "Ask the caller how much they would like to pay per month. "
                    "Remind them the minimum monthly payment is $25."
                ),
                required=True,
            ),
            guava.Field(
                key="card_number",
                field_type="text",
                description=(
                    "Ask the caller for the credit or debit card number they would like "
                    "to use for the monthly payments."
                ),
                required=True,
            ),
            guava.Field(
                key="exp_date",
                field_type="text",
                description=(
                    "Ask for the card expiration date in YYYY-MM format. "
                    "Guide them if needed — for example, a card expiring March 2027 would be 2027-03."
                ),
                required=True,
            ),
            guava.Field(
                key="card_code",
                field_type="text",
                description=(
                    "Ask for the 3 or 4 digit security code on the back of their card."
                ),
                required=True,
            ),
            guava.Field(
                key="billing_address",
                field_type="text",
                description="Ask for the billing street address associated with the card.",
                required=True,
            ),
            guava.Field(
                key="billing_city",
                field_type="text",
                description="Ask for the billing city.",
                required=True,
            ),
            guava.Field(
                key="billing_state",
                field_type="text",
                description="Ask for the two-letter billing state abbreviation.",
                required=True,
            ),
            guava.Field(
                key="billing_zip",
                field_type="text",
                description="Ask for the billing ZIP code.",
                required=True,
            ),
            guava.Field(
                key="start_date",
                field_type="text",
                description=(
                    "Ask the caller what date they would like their first payment to be charged, "
                    "in YYYY-MM-DD format. It must be a future date."
                ),
                required=True,
            ),
            guava.Field(
                key="confirm_enrollment",
                field_type="multiple_choice",
                description=(
                    "Summarize the payment plan to the caller: the monthly amount, start date, "
                    "and estimated number of payments based on their total balance divided by the "
                    "monthly amount. Ask them to confirm they agree to the plan."
                ),
                choices=["yes", "no"],
                required=True,
            ),
        ],
    )


@agent.on_task_complete("payment_plan_enrollment")
def on_done(call: guava.Call) -> None:
    confirm = call.get_field("confirm_enrollment")

    if confirm != "yes":
        call.hangup(
            final_instructions=(
                "Tell the caller that the payment plan enrollment has been cancelled. "
                "Let them know they can call back anytime to set up a plan. Be warm and professional."
            )
        )
        return

    first_name = call.get_field("first_name")
    last_name = call.get_field("last_name")
    email = call.get_field("email")
    phone = call.get_field("phone")
    monthly_payment = call.get_field("monthly_payment")
    card_number = call.get_field("card_number")
    exp_date = call.get_field("exp_date")
    card_code = call.get_field("card_code")
    billing_address = call.get_field("billing_address")
    billing_city = call.get_field("billing_city")
    billing_state = call.get_field("billing_state")
    billing_zip = call.get_field("billing_zip")
    start_date = call.get_field("start_date")
    total_balance_str = call.get_field("total_balance")

    try:
        total_balance = float(total_balance_str.replace("$", "").replace(",", ""))
        monthly_amount = float(monthly_payment.replace("$", "").replace(",", ""))
        total_occurrences = max(1, round(total_balance / monthly_amount))
        monthly_amount_str = f"{monthly_amount:.2f}"
    except (ValueError, ZeroDivisionError) as e:
        logging.error("Amount parsing error: %s", e)
        call.hangup(
            final_instructions=(
                "Apologize to the caller and let them know there was an issue processing their "
                "payment amounts. Ask them to call back so we can assist them properly. "
                "Be empathetic and professional."
            )
        )
        return

    customer_profile_id = None
    payment_profile_id = None
    subscription_id = None
    error_message = None

    try:
        profile_result = create_customer_profile(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            card_number=card_number,
            exp_date=exp_date,
            card_code=card_code,
            address=billing_address,
            city=billing_city,
            state=billing_state,
            zip_code=billing_zip,
        )
        result_code = profile_result.get("messages", {}).get("resultCode", "Error")
        if result_code != "Ok":
            messages = profile_result.get("messages", {}).get("message", [])
            error_text = messages[0].get("text", "unknown error") if messages else "unknown error"
            error_message = f"customer profile creation failed: {error_text}"
        else:
            customer_profile_id = profile_result.get("customerProfileId")
            payment_profile_ids = profile_result.get("customerPaymentProfileIdList", [])
            payment_profile_id = payment_profile_ids[0] if payment_profile_ids else None

            if not customer_profile_id or not payment_profile_id:
                error_message = "customer profile IDs were not returned"
            else:
                sub_result = create_subscription(
                    customer_profile_id=customer_profile_id,
                    payment_profile_id=payment_profile_id,
                    first_name=first_name,
                    last_name=last_name,
                    monthly_amount=monthly_amount_str,
                    total_occurrences=total_occurrences,
                    start_date=start_date,
                )
                sub_code = sub_result.get("messages", {}).get("resultCode", "Error")
                if sub_code != "Ok":
                    sub_messages = sub_result.get("messages", {}).get("message", [])
                    sub_error = sub_messages[0].get("text", "unknown error") if sub_messages else "unknown error"
                    error_message = f"subscription creation failed: {sub_error}"
                else:
                    subscription_id = sub_result.get("subscriptionId")
    except Exception as e:
        logging.error("Authorize.net API error: %s", e)
        error_message = "a system error occurred"

    if error_message:
        call.hangup(
            final_instructions=(
                f"Tell the caller that unfortunately we were unable to complete their payment plan "
                f"enrollment because {error_message}. Apologize sincerely and let them know our billing "
                f"team will follow up with them by email. Be empathetic and professional."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Tell the caller that their payment plan has been successfully set up. "
                f"Their subscription confirmation number is {subscription_id}. "
                f"Let them know their first payment of ${monthly_amount_str} will be charged on {start_date}, "
                f"and they will receive a confirmation email at {email}. "
                f"Thank them for choosing Harbor Health Services and wish them well. "
                f"Be warm and professional."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
