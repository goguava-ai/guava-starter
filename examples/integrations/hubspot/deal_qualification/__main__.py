import guava
import os
import logging
import requests

logging.basicConfig(level=logging.INFO)

HUBSPOT_ACCESS_TOKEN = os.environ["HUBSPOT_ACCESS_TOKEN"]
HEADERS = {
    "Authorization": f"Bearer {HUBSPOT_ACCESS_TOKEN}",
    "Content-Type": "application/json",
}
BASE_URL = "https://api.hubapi.com"


def upsert_contact(email: str, firstname: str, lastname: str, company: str) -> str:
    """Creates or updates a HubSpot contact by email. Returns the contact ID."""
    payload = {
        "inputs": [
            {
                "idProperty": "email",
                "id": email,
                "properties": {
                    "email": email,
                    "firstname": firstname,
                    "lastname": lastname,
                    "company": company,
                    "lifecyclestage": "lead",
                },
            }
        ]
    }
    resp = requests.post(
        f"{BASE_URL}/crm/objects/2026-03/contacts/batch/upsert",
        headers=HEADERS,
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["results"][0]["id"]


def create_deal(contact_id: str, dealname: str, stage: str, description: str) -> str:
    """Creates a deal associated with the given contact. Returns the deal ID."""
    payload = {
        "properties": {
            "dealname": dealname,
            "dealstage": stage,
            "pipeline": "default",
            "description": description,
        },
        "associations": [
            {
                "to": {"id": contact_id},
                "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 3}],
            }
        ],
    }
    resp = requests.post(
        f"{BASE_URL}/crm/objects/2026-03/deals",
        headers=HEADERS,
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["id"]


class DealQualificationController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Apex Solutions",
            agent_name="Jordan",
            agent_purpose=(
                "to have a friendly discovery conversation with inbound prospects and qualify "
                "them for the Apex Solutions sales team"
            ),
        )

        self.set_task(
            objective=(
                "A prospect has called Apex Solutions for a discovery call. "
                "Conduct a natural BANT qualification: understand their Budget, Authority, "
                "Need, and Timeline. Collect contact details and create a deal in HubSpot."
            ),
            checklist=[
                guava.Say(
                    "Thanks for calling Apex Solutions. I'm Jordan. "
                    "I'd love to learn more about your situation and see how we might be able to help. "
                    "Do you have a few minutes to chat?"
                ),
                guava.Field(
                    key="caller_name",
                    field_type="text",
                    description="Ask for their full name.",
                    required=True,
                ),
                guava.Field(
                    key="caller_email",
                    field_type="text",
                    description="Ask for their business email address.",
                    required=True,
                ),
                guava.Field(
                    key="company_name",
                    field_type="text",
                    description="Ask what company they represent.",
                    required=True,
                ),
                guava.Field(
                    key="pain_point",
                    field_type="text",
                    description=(
                        "Ask what challenge or problem they're trying to solve. "
                        "Probe naturally: 'What's the main challenge you're hoping we could help with?'"
                    ),
                    required=True,
                ),
                guava.Field(
                    key="decision_role",
                    field_type="multiple_choice",
                    description=(
                        "Ask about their role in the buying decision. "
                        "Frame it naturally: 'Are you the one who would typically sign off on "
                        "a solution like this, or would others be involved in that decision?'"
                    ),
                    choices=[
                        "sole decision maker",
                        "part of a committee",
                        "influencer/evaluator",
                        "not the decision maker",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="budget",
                    field_type="multiple_choice",
                    description=(
                        "Ask if they have budget allocated. "
                        "Be tactful: 'Have you set aside a budget for this initiative yet?'"
                    ),
                    choices=[
                        "yes/allocated",
                        "yes/not yet approved",
                        "exploring what's available",
                        "no budget yet",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="timeline",
                    field_type="multiple_choice",
                    description="Ask when they would ideally like a solution in place.",
                    choices=[
                        "within 30 days",
                        "1–3 months",
                        "3–6 months",
                        "6+ months",
                        "no set timeline",
                    ],
                    required=True,
                ),
            ],
            on_complete=self.qualify_and_record,
        )

        self.accept_call()

    def qualify_and_record(self):
        name = self.get_field("caller_name") or "Unknown"
        email = self.get_field("caller_email") or ""
        company = self.get_field("company_name") or ""
        pain_point = self.get_field("pain_point") or ""
        decision_role = self.get_field("decision_role") or ""
        budget = self.get_field("budget") or ""
        timeline = self.get_field("timeline") or ""

        parts = name.strip().split(" ", 1)
        firstname = parts[0]
        lastname = parts[1] if len(parts) > 1 else ""
        dealname = (
            f"{company} — Inbound Qualification"
            if company
            else f"{name} — Inbound Qualification"
        )

        qual_notes = (
            f"BANT Qualification\n"
            f"Need: {pain_point}\n"
            f"Authority: {decision_role}\n"
            f"Budget: {budget}\n"
            f"Timeline: {timeline}"
        )

        # Fully qualified: budget exists and timeline is within 6 months
        is_qualified = (
            budget in ("yes/allocated", "yes/not yet approved")
            and timeline not in ("6+ months", "no set timeline")
        )

        stage = "qualifiedtobuy" if is_qualified else "appointmentscheduled"
        logging.info(
            "Qualification for %s (%s): is_qualified=%s, stage=%s",
            name, email, is_qualified, stage,
        )

        try:
            contact_id = upsert_contact(email, firstname, lastname, company)
            deal_id = create_deal(contact_id, dealname, stage, qual_notes)
            logging.info("Created deal %s for contact %s", deal_id, contact_id)

            if is_qualified:
                self.hangup(
                    final_instructions=(
                        f"Thank {name} for their time and the great conversation. "
                        "Let them know they sound like an excellent fit for Apex Solutions "
                        "and that a senior sales executive will be in touch within 24 hours "
                        "to schedule a tailored demo. Express genuine enthusiasm."
                    )
                )
            else:
                self.hangup(
                    final_instructions=(
                        f"Thank {name} warmly for their time. "
                        "Let them know their information has been passed to our team "
                        "and someone will follow up when the timing is right. "
                        "Offer to send resources by email in the meantime. Wish them well."
                    )
                )
        except Exception as e:
            logging.error("Failed to record qualification in HubSpot: %s", e)
            self.hangup(
                final_instructions=(
                    f"Thank {name} for their time and apologize for a brief technical issue. "
                    "Let them know a team member will follow up by end of day. Wish them a great day."
                )
            )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=DealQualificationController,
    )
