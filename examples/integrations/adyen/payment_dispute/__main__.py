import logging
import os

import guava
import requests
from guava import logging_utils

ADYEN_API_KEY = os.environ["ADYEN_API_KEY"]
ADYEN_MERCHANT_ACCOUNT = os.environ["ADYEN_MERCHANT_ACCOUNT"]
BASE_URL = "https://checkout-test.adyen.com/v71"

HEADERS = {
    "X-API-Key": ADYEN_API_KEY,
    "Content-Type": "application/json",
}


agent = guava.Agent(
    name="Marcus",
    organization="Meridian Retail",
    purpose="to help customers understand and resolve disputed charges",
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "collect_dispute_details",
        objective=(
            "Collect the customer's dispute details, explain the dispute resolution process, "
            "and — if they choose to accept liability — submit an acceptance via the Adyen API."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Meridian Retail. This is Marcus from our payments "
                "support team. I understand you have a question about a disputed charge — "
                "I'm here to help."
            ),
            guava.Field(
                key="dispute_psp_reference",
                field_type="text",
                description=(
                    "Ask the customer for the dispute PSP reference or the original payment "
                    "reference associated with the charge they are disputing. This is usually "
                    "found on their bank statement or in any dispute notification email they received."
                ),
                required=True,
            ),
            guava.Field(
                key="dispute_reason",
                field_type="multiple_choice",
                description=(
                    "Ask the customer to select the reason they are disputing the charge."
                ),
                choices=[
                    "unauthorized transaction",
                    "item not received",
                    "item not as described",
                    "duplicate charge",
                    "subscription cancelled but still charged",
                    "other",
                ],
                required=True,
            ),
            guava.Say(
                "Explain the dispute resolution process: Meridian Retail will review the "
                "evidence on both sides, which typically takes 5 to 10 business days. "
                "If the dispute is upheld, the customer will receive a full refund. "
                "However, if the customer now believes the charge was valid and they wish "
                "to withdraw the dispute, they can do that now. Ask if they have any questions."
            ),
            guava.Field(
                key="accept_liability",
                field_type="multiple_choice",
                description=(
                    "Ask the customer whether they would like to accept liability for this dispute "
                    "— meaning they acknowledge the charge was valid and wish to withdraw the dispute. "
                    "Or, ask if they want to continue with the dispute review."
                ),
                choices=["accept liability and withdraw dispute", "continue with dispute review"],
                required=True,
            ),
        ],
    )


@agent.on_task_complete("collect_dispute_details")
def handle_complete(call: guava.Call) -> None:
    dispute_psp_reference = call.get_field("dispute_psp_reference").strip()
    dispute_reason = call.get_field("dispute_reason")
    accept_liability = call.get_field("accept_liability")

    logging.info(
        "Dispute call complete. PSP ref: %s, reason: %s, decision: %s",
        dispute_psp_reference,
        dispute_reason,
        accept_liability,
    )

    if accept_liability == "accept liability and withdraw dispute":
        try:
            resp = requests.post(
                f"{BASE_URL}/disputes/{dispute_psp_reference}/accept",
                headers=HEADERS,
                json={
                    "merchantAccount": ADYEN_MERCHANT_ACCOUNT,
                },
                timeout=15,
            )
            resp.raise_for_status()
            result = resp.json()
            logging.info("Dispute acceptance response: %s", result)
            accepted = True
        except requests.exceptions.HTTPError as e:
            logging.error(
                "Adyen dispute accept HTTP error: %s — %s",
                e,
                e.response.text if e.response else "",
            )
            accepted = False
        except Exception as e:
            logging.error("Adyen dispute accept error: %s", e)
            accepted = False

        if accepted:
            call.hangup(
                final_instructions=(
                    "Tell the caller that their dispute has been successfully withdrawn and "
                    "the original charge will stand. No further action is needed on their part. "
                    "Thank them for contacting Meridian Retail and wish them a good day."
                )
            )
        else:
            call.hangup(
                final_instructions=(
                    "Apologize to the caller and let them know we were unable to process the "
                    "dispute withdrawal automatically at this time. A specialist from our payments "
                    "team will follow up within one business day. They can also reach us at "
                    "payments@meridianretail.com. Thank them for their patience."
                )
            )
    else:
        call.hangup(
            final_instructions=(
                "Tell the caller that their dispute has been noted and our payments team will "
                "review it within 5 to 10 business days. They will receive an email notification "
                "once a decision has been made. Let them know they can reach us anytime at "
                "1-800-555-0147 or at disputes@meridianretail.com. Thank them for calling."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
