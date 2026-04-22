import logging
import os

import guava
import requests
from guava import logging_utils

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


def get_transaction_details(trans_id: str):
    payload = {
        "getTransactionDetailsRequest": {
            "merchantAuthentication": auth_block(),
            "transId": trans_id,
        }
    }
    resp = requests.post(BASE_URL, json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()


def issue_refund(trans_id: str, amount: str, last_four: str, exp_date: str):
    payload = {
        "createTransactionRequest": {
            "merchantAuthentication": auth_block(),
            "transactionRequest": {
                "transactionType": "refundTransaction",
                "amount": amount,
                "payment": {
                    "creditCard": {
                        "cardNumber": last_four,
                        "expirationDate": exp_date,
                    }
                },
                "refTransId": trans_id,
            },
        }
    }
    resp = requests.post(BASE_URL, json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()


agent = guava.Agent(
    name="Maya",
    organization="Crestview Dental",
    purpose="to help patients process refund requests",
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "refund_request",
        objective="Help the patient request a refund for a charge on their account.",
        checklist=[
            guava.Say(
                "Thank you for calling Crestview Dental billing support. "
                "My name is Maya and I can help you with a refund request today."
            ),
            guava.Field(
                key="transaction_id",
                field_type="text",
                description=(
                    "Ask the caller for their transaction ID or order number. "
                    "It is typically a 10 to 12 digit number found on their receipt or billing statement."
                ),
                required=True,
            ),
            guava.Field(
                key="last_four",
                field_type="text",
                description=(
                    "Ask for the last four digits of the card used for this transaction."
                ),
                required=True,
            ),
            guava.Field(
                key="refund_reason",
                field_type="multiple_choice",
                description="Ask the caller why they are requesting a refund.",
                choices=[
                    "duplicate charge",
                    "services not rendered",
                    "incorrect amount",
                    "other",
                ],
                required=True,
            ),
            guava.Field(
                key="confirm_refund",
                field_type="multiple_choice",
                description=(
                    "Confirm with the caller that they would like to proceed with the refund. "
                    "Tell them you will look up their transaction and process the refund now."
                ),
                choices=["yes", "no"],
                required=True,
            ),
        ],
    )


@agent.on_task_complete("refund_request")
def on_done(call: guava.Call) -> None:
    transaction_id = call.get_field("transaction_id")
    last_four = call.get_field("last_four")
    confirm = call.get_field("confirm_refund")

    if confirm != "yes":
        call.hangup(
            final_instructions=(
                "Tell the caller that their refund request has been cancelled at their request "
                "and they are welcome to call back if they change their mind. Be warm and professional."
            )
        )
        return

    transaction_details = None
    refund_result = None
    error_message = None

    try:
        transaction_details = get_transaction_details(transaction_id)
        result_code = transaction_details.get("messages", {}).get("resultCode", "Error")
        if result_code != "Ok":
            error_message = "transaction not found"
        else:
            txn = transaction_details.get("transaction", {})
            status = txn.get("transactionStatus", "")
            if status != "settledSuccessfully":
                friendly = status.replace("_", " ") if status else "unknown"
                call.hangup(
                    final_instructions=(
                        f"Let the caller know their transaction currently has a status of "
                        f"'{friendly}' and a refund cannot be issued at this time — refunds are "
                        f"only available on fully settled transactions. If they believe this is an "
                        f"error, let them know they can call our billing team. Be empathetic and helpful."
                    )
                )
                return

            amount = str(txn.get("settleAmount", txn.get("authAmount", "0.00")))
            payment = txn.get("payment", {})
            credit_card = payment.get("creditCard", {})
            exp_date = credit_card.get("expirationDate", "XXXX")

            refund_result = issue_refund(
                trans_id=transaction_id,
                amount=amount,
                last_four=last_four,
                exp_date=exp_date,
            )
            refund_code = refund_result.get("messages", {}).get("resultCode", "Error")
            if refund_code != "Ok":
                trans_response = refund_result.get("transactionResponse", {})
                errors = trans_response.get("errors", [])
                if errors:
                    error_message = errors[0].get("errorText", "unknown error")
                else:
                    error_message = "refund could not be processed"
    except Exception as e:
        logging.error("Authorize.net API error: %s", e)
        error_message = "a system error occurred"

    if error_message:
        call.hangup(
            final_instructions=(
                f"Tell the caller that unfortunately we were unable to process their refund "
                f"because {error_message}. Apologize sincerely and let them know they can call back "
                f"or visit the office for further assistance. Be empathetic and professional."
            )
        )
    else:
        trans_id_out = (
            refund_result.get("transactionResponse", {}).get("transId", "N/A")
            if refund_result
            else "N/A"
        )
        call.hangup(
            final_instructions=(
                f"Tell the caller that their refund has been successfully submitted and the "
                f"refund confirmation number is {trans_id_out}. Let them know refunds typically "
                f"appear on their statement within 3 to 5 business days. Thank them for their "
                f"patience and wish them a great day. Be warm and professional."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
