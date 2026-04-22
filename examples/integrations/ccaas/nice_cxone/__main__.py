import guava
import os
import logging
import json
import requests
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)


class InboundSupportTriageController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Apex Solutions - Customer Support",
            agent_name="Morgan",
            agent_purpose=(
                "to greet customers calling in with issues, collect their details and "
                "categorize the problem so it can be routed to the right team quickly"
            ),
        )

        self.set_task(
            objective=(
                "A customer has called Apex Solutions support. Greet them warmly, "
                "collect all the information needed to create a contact record and "
                "route the issue, and let them know the right team will follow up."
            ),
            checklist=[
                guava.Say(
                    "Thank you for calling Apex Solutions Customer Support. My name is Morgan "
                    "and I'll be helping you today. Let me collect some information so we can "
                    "get you the right help as quickly as possible."
                ),
                guava.Field(
                    key="caller_name",
                    description="Ask the caller for their full name.",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="account_number",
                    description=(
                        "Ask the caller for their account number. If they don't have it, "
                        "ask for the email address on file."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="issue_category",
                    description=(
                        "Ask the caller to describe their issue. Based on their answer, "
                        "categorize it as one of: billing, technical, account_access, "
                        "product_inquiry, or other."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="issue_description",
                    description=(
                        "Ask the caller to describe the issue in detail. Capture a clear "
                        "summary of the problem in their own words."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="urgency",
                    description=(
                        "Ask the caller how urgent the issue is — is it preventing them "
                        "from using the product right now, or is it something that can wait? "
                        "Categorize as: critical, high, medium, or low."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="callback_number",
                    description=(
                        "Ask the caller for the best phone number to reach them if a "
                        "follow-up call is needed. Confirm the number back to them."
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
            "agent": "Morgan",
            "organization": "Apex Solutions - Customer Support",
            "use_case": "inbound_support_triage",
            "fields": {
                "caller_name": self.get_field("caller_name"),
                "account_number": self.get_field("account_number"),
                "issue_category": self.get_field("issue_category"),
                "issue_description": self.get_field("issue_description"),
                "urgency": self.get_field("urgency"),
                "callback_number": self.get_field("callback_number"),
            },
        }
        print(json.dumps(results, indent=2))
        logging.info("Support triage results saved locally.")

        # Push contact record to NICE CXone
        try:
            base_url = os.environ["CXONE_BASE_URL"]
            token = os.environ["CXONE_ACCESS_TOKEN"]
            skill_id = os.environ["CXONE_SKILL_ID"]
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            contact_payload = {
                "skillId": skill_id,
                "mediaType": "phone",
                "firstName": self.get_field("caller_name"),
                "phone1": self.get_field("callback_number"),
            }
            contact_resp = requests.post(
                f"{base_url}/incontactapi/services/v30.0/contacts",
                headers=headers,
                json=contact_payload,
                timeout=10,
            )
            contact_resp.raise_for_status()
            contact_id = contact_resp.json().get("contactId")
            logging.info("CXone contact created: %s", contact_id)

            if contact_id:
                custom_data = {
                    "indicatorName": "GuavaCallData",
                    "indicatorValue": json.dumps({
                        "account_number": self.get_field("account_number"),
                        "issue_category": self.get_field("issue_category"),
                        "issue_description": self.get_field("issue_description"),
                        "urgency": self.get_field("urgency"),
                    }),
                }
                custom_resp = requests.post(
                    f"{base_url}/incontactapi/services/v30.0/contacts/{contact_id}/custom-data",
                    headers=headers,
                    json=custom_data,
                    timeout=10,
                )
                custom_resp.raise_for_status()
                logging.info("CXone custom data attached to contact %s", contact_id)
        except Exception as e:
            logging.error("Failed to push to CXone: %s", e)

        self.hangup(
            final_instructions=(
                "Let the customer know that their issue has been logged and a specialist "
                "from the appropriate team will follow up within 1 business hour at the "
                "callback number provided. Thank them for calling Apex Solutions and wish "
                "them a good day."
            )
        )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=InboundSupportTriageController,
    )
