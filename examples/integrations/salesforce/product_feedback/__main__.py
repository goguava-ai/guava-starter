import logging
import os

import guava
import requests
from guava import logging_utils

SALESFORCE_INSTANCE_URL = os.environ["SALESFORCE_INSTANCE_URL"]
SALESFORCE_ACCESS_TOKEN = os.environ["SALESFORCE_ACCESS_TOKEN"]
SF_HEADERS = {
    "Authorization": f"Bearer {SALESFORCE_ACCESS_TOKEN}",
    "Content-Type": "application/json",
}
API_BASE = f"{SALESFORCE_INSTANCE_URL}/services/data/v66.0"


def find_contact_by_email(email: str) -> dict | None:
    q = (
        "SELECT Id, FirstName, LastName, AccountId "
        f"FROM Contact WHERE Email = '{email}' LIMIT 1"
    )
    resp = requests.get(
        f"{API_BASE}/query",
        headers=SF_HEADERS,
        params={"q": q},
        timeout=10,
    )
    resp.raise_for_status()
    records = resp.json().get("records", [])
    return records[0] if records else None


def create_feedback_case(contact_id: str, account_id: str, subject: str, description: str, feedback_type: str) -> str:
    """Creates a Case to track the product feedback. Returns the case ID."""
    payload = {
        "ContactId": contact_id,
        "AccountId": account_id,
        "Subject": subject,
        "Description": description,
        "Status": "New",
        "Origin": "Phone",
        "Priority": "Medium",
        "Type": feedback_type,
        "Reason": "Product Feedback",
    }
    resp = requests.post(
        f"{API_BASE}/sobjects/Case",
        headers=SF_HEADERS,
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("id", "")


def create_product_idea(contact_id: str, account_id: str, title: str, body: str) -> None:
    """Creates a FeedItem (Chatter post) on the account to surface the idea internally."""
    payload = {
        "ParentId": account_id,
        "Body": f"[Product Idea from {contact_id}]\n\n{title}\n\n{body}",
        "Type": "TextPost",
        "Visibility": "AllUsers",
    }
    resp = requests.post(
        f"{API_BASE}/sobjects/FeedItem",
        headers=SF_HEADERS,
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()


agent = guava.Agent(
    name="Taylor",
    organization="Helix Platform",
    purpose=(
        "to collect structured product feedback and feature requests from Helix Platform "
        "customers and route them to the right team"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "log_feedback",
        objective=(
            "A customer has called to share product feedback or a feature request. "
            "Greet them warmly, collect their contact details, and capture their feedback "
            "in enough detail to be actionable for the product team."
        ),
        checklist=[
            guava.Say(
                "Thanks for calling Helix Platform. I'm Taylor, and I'd love to hear "
                "your feedback. Customer input directly shapes our product roadmap, "
                "so your thoughts are genuinely valuable."
            ),
            guava.Field(
                key="caller_email",
                field_type="text",
                description="Ask for the email address on their account so we can follow up.",
                required=True,
            ),
            guava.Field(
                key="feedback_type",
                field_type="multiple_choice",
                description="Ask what type of feedback they have.",
                choices=[
                    "feature request",
                    "bug report",
                    "usability concern",
                    "performance issue",
                    "general praise",
                ],
                required=True,
            ),
            guava.Field(
                key="product_area",
                field_type="multiple_choice",
                description="Ask which area of the product their feedback relates to.",
                choices=[
                    "dashboard / reporting",
                    "integrations",
                    "mobile app",
                    "API / developer tools",
                    "billing / account management",
                    "notifications / alerts",
                    "other",
                ],
                required=True,
            ),
            guava.Field(
                key="feedback_detail",
                field_type="text",
                description=(
                    "Ask them to describe their feedback in their own words. "
                    "Encourage them to be specific — what is the problem, what would the "
                    "ideal solution look like, and how often does this affect them?"
                ),
                required=True,
            ),
            guava.Field(
                key="business_impact",
                field_type="multiple_choice",
                description=(
                    "Ask how much this impacts their daily work. "
                    "'Just so our product team understands the priority, how much does this "
                    "affect your work today?'"
                ),
                choices=["blocks my work entirely", "significant daily friction", "minor inconvenience", "nice to have"],
                required=True,
            ),
            guava.Field(
                key="okay_to_contact",
                field_type="multiple_choice",
                description=(
                    "Ask if the product team can reach out to them for a deeper conversation "
                    "if needed. Keep it optional."
                ),
                choices=["yes", "no"],
                required=True,
            ),
        ],
    )


@agent.on_task_complete("log_feedback")
def on_done(call: guava.Call) -> None:
    email = call.get_field("caller_email") or ""
    feedback_type = call.get_field("feedback_type") or "general feedback"
    product_area = call.get_field("product_area") or "other"
    detail = call.get_field("feedback_detail") or ""
    impact = call.get_field("business_impact") or ""
    ok_to_contact = call.get_field("okay_to_contact") or "no"

    logging.info("Looking up contact by email: %s", email)
    try:
        contact = find_contact_by_email(email)
    except Exception as e:
        logging.error("Contact lookup failed: %s", e)
        contact = None

    subject = f"{feedback_type.title()} — {product_area.title()}"
    description = (
        f"Feedback type: {feedback_type}\n"
        f"Product area: {product_area}\n"
        f"Business impact: {impact}\n"
        f"Open to follow-up: {ok_to_contact}\n\n"
        f"Feedback:\n{detail}"
    )

    first_name = "there"
    if contact:
        contact_id = contact["Id"]
        account_id = contact.get("AccountId") or ""
        first_name = contact.get("FirstName") or "there"

        logging.info("Creating feedback Case for contact %s.", contact_id)
        case_id = ""
        try:
            sf_type = "Feature Request" if feedback_type == "feature request" else "Problem"
            case_id = create_feedback_case(contact_id, account_id, subject, description, sf_type)
            logging.info("Case created: %s", case_id)
        except Exception as e:
            logging.error("Failed to create Case: %s", e)

        if feedback_type == "feature request" and account_id:
            try:
                create_product_idea(contact_id, account_id, subject, detail)
                logging.info("Chatter FeedItem created for feature request.")
            except Exception as e:
                logging.warning("Could not create FeedItem (Chatter may be disabled): %s", e)

        call.hangup(
            final_instructions=(
                f"Thank {first_name} sincerely for taking the time to share their feedback. "
                "Let them know it has been recorded and passed to the product team. "
                + (f"Mention that their case reference number is {case_id}. " if case_id else "")
                + ("Let them know the product team may reach out for a deeper conversation. "
                   if ok_to_contact == "yes" else "")
                + "Wish them a great day."
            )
        )
    else:
        logging.warning("No Salesforce Contact found for email %s.", email)
        call.hangup(
            final_instructions=(
                "Thank the caller for their feedback and let them know it has been noted. "
                "Mention that a member of the team will follow up if they'd like to discuss further. "
                "Wish them a great day."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
