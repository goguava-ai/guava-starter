import guava
import os
import logging
import base64
import requests

logging.basicConfig(level=logging.INFO)

ZENDESK_SUBDOMAIN = os.environ["ZENDESK_SUBDOMAIN"]
ZENDESK_EMAIL = os.environ["ZENDESK_EMAIL"]
ZENDESK_API_TOKEN = os.environ["ZENDESK_API_TOKEN"]

# The Zendesk group ID for your Tier-2 / escalations team.
# Find it at Admin Center → People → Groups → click the group → copy the ID from the URL.
ESCALATION_GROUP_ID = int(os.environ["ZENDESK_ESCALATION_GROUP_ID"])

_encoded = base64.b64encode(f"{ZENDESK_EMAIL}/token:{ZENDESK_API_TOKEN}".encode()).decode()
HEADERS = {
    "Authorization": f"Basic {_encoded}",
    "Content-Type": "application/json",
}
BASE_URL = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com/api/v2"

# Keywords that indicate a business-critical or production-down situation.
CRITICAL_KEYWORDS = [
    "down", "outage", "production", "data loss", "breach", "security",
    "revenue", "customers affected", "cannot login", "not working for everyone",
]


def create_escalated_ticket(
    subject: str,
    body: str,
    requester_name: str,
    requester_email: str,
    business_impact: str,
) -> dict:
    """
    Creates an urgent ticket assigned directly to the escalation group.
    Tags it with 'escalated' and 'voice' for easy Zendesk view filtering.
    """
    payload = {
        "ticket": {
            "subject": f"[ESCALATED] {subject}",
            "comment": {
                "body": (
                    f"{body}\n\n"
                    f"--- Escalation context ---\n"
                    f"Business impact: {business_impact}\n"
                    f"Caller: {requester_name} ({requester_email})\n"
                    "Source: Inbound phone call — escalation requested by caller"
                )
            },
            "requester": {"name": requester_name, "email": requester_email},
            "priority": "urgent",
            "type": "incident",
            "group_id": ESCALATION_GROUP_ID,
            "tags": ["escalated", "voice", "guava"],
        }
    }
    resp = requests.post(f"{BASE_URL}/tickets", headers=HEADERS, json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json()["ticket"]


def is_critical(description: str, impact: str) -> bool:
    """Returns True if the issue description or impact contains critical keywords."""
    combined = f"{description} {impact}".lower()
    return any(kw in combined for kw in CRITICAL_KEYWORDS)


class EscalationController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Horizon Software",
            agent_name="Jordan",
            agent_purpose=(
                "to triage urgent support issues and escalate them directly to the "
                "Horizon Software senior support team"
            ),
        )

        self.set_task(
            objective=(
                "A customer has called with what they believe is an urgent or critical issue. "
                "Collect their details and enough information to determine if escalation is warranted, "
                "then create a high-priority ticket for the senior support team."
            ),
            checklist=[
                guava.Say(
                    "Thank you for calling Horizon Software support. My name is Jordan. "
                    "I understand you have an urgent issue — I'm here to help get this "
                    "escalated to the right team immediately."
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
                    description="Ask for their email address.",
                    required=True,
                ),
                guava.Field(
                    key="company_name",
                    field_type="text",
                    description="Ask for the name of their company or organization.",
                    required=True,
                ),
                guava.Field(
                    key="issue_description",
                    field_type="text",
                    description=(
                        "Ask them to describe the issue they're experiencing. "
                        "Capture their description in full."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="business_impact",
                    field_type="text",
                    description=(
                        "Ask how this issue is impacting their business right now — "
                        "for example: is it affecting all users, blocking revenue, or causing data loss? "
                        "Capture their answer."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="users_affected",
                    field_type="multiple_choice",
                    description=(
                        "Ask approximately how many users or customers are currently affected."
                    ),
                    choices=["just me", "a few users", "my whole team", "all of our customers"],
                    required=True,
                ),
                guava.Field(
                    key="callback_number",
                    field_type="text",
                    description=(
                        "Ask for the best phone number for our senior support engineer to call them back. "
                        "Capture in E.164 format if possible."
                    ),
                    required=True,
                ),
            ],
            on_complete=self.escalate,
        )

        self.accept_call()

    def escalate(self):
        name = self.get_field("caller_name") or "Unknown Caller"
        email = self.get_field("caller_email") or ""
        company = self.get_field("company_name") or ""
        description = self.get_field("issue_description") or "Urgent issue reported by phone"
        impact = self.get_field("business_impact") or ""
        users_affected = self.get_field("users_affected") or ""
        callback = self.get_field("callback_number") or ""

        subject = f"Urgent issue — {company}" if company else "Urgent issue reported by phone"
        body = (
            f"{description}\n\n"
            f"Company: {company}\n"
            f"Users affected: {users_affected}\n"
            f"Callback number: {callback}"
        )

        critical = is_critical(description, impact)
        if critical:
            logging.info("Critical keywords detected — marking as production incident")

        logging.info("Creating escalated ticket for %s (%s)", name, email)
        try:
            ticket = create_escalated_ticket(
                subject=subject,
                body=body,
                requester_name=name,
                requester_email=email,
                business_impact=impact,
            )
            ticket_id = ticket["id"]
            logging.info("Escalated ticket created: #%s", ticket_id)

            self.hangup(
                final_instructions=(
                    f"Let {name} know their issue has been escalated to our senior support team "
                    f"as ticket #{ticket_id} with urgent priority. "
                    "A senior support engineer will call them back at the number they provided "
                    "as soon as possible — typically within 30 minutes for urgent cases. "
                    "They will also receive an email confirmation. "
                    + (
                        "Acknowledge that this appears to be a critical production issue and "
                        "assure them the team is being paged immediately. "
                        if critical
                        else ""
                    )
                    + "Thank them for calling and apologize for the disruption."
                )
            )
        except Exception as e:
            logging.error("Failed to create escalated ticket: %s", e)
            self.hangup(
                final_instructions=(
                    f"Apologize to {name} and let them know there was a technical issue creating "
                    "the ticket. Give them the direct escalation email: escalations@horizonsoftware.com "
                    "and ask them to send the details there immediately. Thank them for their patience."
                )
            )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=EscalationController,
    )
