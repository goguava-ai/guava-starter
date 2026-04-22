import guava
import os
import logging
import json
import requests
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)


class InboundBillingInquiryController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Clearview Utilities - Billing Department",
            agent_name="Taylor",
            agent_purpose=(
                "to assist customers with billing questions, resolve billing issues, "
                "and ensure accurate records are maintained in the contact system"
            ),
        )

        self.set_task(
            objective=(
                "A customer has called Clearview Utilities about a billing issue. Greet "
                "them warmly, identify the billing concern, work toward a resolution, "
                "and log the interaction."
            ),
            checklist=[
                guava.Say(
                    "Thank you for calling Clearview Utilities Billing Department. My name "
                    "is Taylor and I'm here to help with any billing questions you have."
                ),
                guava.Field(
                    key="caller_name",
                    description="Ask the caller for their full name.",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="account_id",
                    description=(
                        "Ask the caller for their Clearview Utilities account ID. "
                        "If they don't have it, ask for the service address on the account."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="billing_issue_type",
                    description=(
                        "Ask what billing issue they're experiencing. Categorize as: "
                        "unexpected_charge, payment_failed, plan_change, refund_request, "
                        "billing_cycle, or other."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="billing_details",
                    description=(
                        "Ask the caller to describe the billing issue in detail — including "
                        "amounts, dates, or specific charges if applicable. Capture a clear summary."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="resolution_status",
                    description=(
                        "Based on the conversation, capture the resolution status: "
                        "resolved, escalated, pending_review, or requires_callback."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="follow_up_needed",
                    description=(
                        "Determine if any follow-up is needed. Capture yes or no, "
                        "and if yes, a brief note on what follow-up is required."
                    ),
                    field_type="text",
                    required=True,
                ),
            ],
            on_complete=self.save_results,
        )

        self.accept_call()

    def save_results(self):
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": "Taylor",
            "organization": "Clearview Utilities - Billing Department",
            "use_case": "inbound_billing_inquiry",
            "fields": {
                "caller_name": self.get_field("caller_name"),
                "account_id": self.get_field("account_id"),
                "billing_issue_type": self.get_field("billing_issue_type"),
                "billing_details": self.get_field("billing_details"),
                "resolution_status": self.get_field("resolution_status"),
                "follow_up_needed": self.get_field("follow_up_needed"),
            },
        }
        print(json.dumps(results, indent=2))
        logging.info("Billing inquiry results saved locally.")

        # Push contact and interaction to Talkdesk
        try:
            base_url = os.environ["TALKDESK_BASE_URL"]
            api_key = os.environ["TALKDESK_API_KEY"]
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }

            # Step 1: Create contact
            contact_payload = {
                "name": self.get_field("caller_name"),
                "customFields": {
                    "account_id": self.get_field("account_id"),
                },
            }
            contact_resp = requests.post(
                f"{base_url}/contacts",
                headers=headers,
                json=contact_payload,
                timeout=10,
            )
            contact_resp.raise_for_status()
            contact_id = contact_resp.json().get("id")
            logging.info("Talkdesk contact created: %s", contact_id)

            # Step 2: Create interaction referencing contact
            interaction_payload = {
                "contactId": contact_id,
                "channel": "voice",
                "direction": "inbound",
                "notes": json.dumps({
                    "billing_issue_type": self.get_field("billing_issue_type"),
                    "billing_details": self.get_field("billing_details"),
                    "resolution_status": self.get_field("resolution_status"),
                    "follow_up_needed": self.get_field("follow_up_needed"),
                }),
                "disposition": self.get_field("resolution_status"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source": "guava_voice_agent",
            }
            interaction_resp = requests.post(
                f"{base_url}/interactions",
                headers=headers,
                json=interaction_payload,
                timeout=10,
            )
            interaction_resp.raise_for_status()
            logging.info("Talkdesk interaction created for contact %s", contact_id)
        except Exception as e:
            logging.error("Failed to push to Talkdesk: %s", e)

        self.hangup(
            final_instructions=(
                "Summarize the resolution or next steps for the customer's billing issue. "
                "If follow-up is needed, let them know when to expect it. Thank them for "
                "calling Clearview Utilities and wish them a good day."
            )
        )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=InboundBillingInquiryController,
    )
