import guava
import os
import logging
from guava import logging_utils
import requests


ADYEN_API_KEY = os.environ["ADYEN_API_KEY"]
ADYEN_MERCHANT_ACCOUNT = os.environ["ADYEN_MERCHANT_ACCOUNT"]
BASE_URL = "https://checkout-test.adyen.com/v71"

HEADERS = {
    "X-API-Key": ADYEN_API_KEY,
    "Content-Type": "application/json",
}


class PaymentDisputeController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Meridian Retail",
            agent_name="Marcus",
            agent_purpose="to help customers understand and resolve disputed charges",
        )

        self.set_task(
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
            on_complete=self.handle_complete,
        )

        self.accept_call()

    def handle_complete(self):
        dispute_psp_reference = self.get_field("dispute_psp_reference").strip()
        dispute_reason = self.get_field("dispute_reason")
        accept_liability = self.get_field("accept_liability")

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
                self.hangup(
                    final_instructions=(
                        "Tell the caller that their dispute has been successfully withdrawn and "
                        "the original charge will stand. No further action is needed on their part. "
                        "Thank them for contacting Meridian Retail and wish them a good day."
                    )
                )
            else:
                self.hangup(
                    final_instructions=(
                        "Apologize to the caller and let them know we were unable to process the "
                        "dispute withdrawal automatically at this time. A specialist from our payments "
                        "team will follow up within one business day. They can also reach us at "
                        "payments@meridianretail.com. Thank them for their patience."
                    )
                )
        else:
            self.hangup(
                final_instructions=(
                    "Tell the caller that their dispute has been noted and our payments team will "
                    "review it within 5 to 10 business days. They will receive an email notification "
                    "once a decision has been made. Let them know they can reach us anytime at "
                    "1-800-555-0147 or at disputes@meridianretail.com. Thank them for calling."
                )
            )


if __name__ == "__main__":
    logging_utils.configure_logging()
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=PaymentDisputeController,
    )
