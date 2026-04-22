import guava
import os
import logging
from guava import logging_utils
import requests
from datetime import datetime, timezone


ZAPIER_WEBHOOK_URL = os.environ["ZAPIER_WEBHOOK_URL"]


def trigger_zap(payload: dict) -> None:
    resp = requests.post(ZAPIER_WEBHOOK_URL, json=payload, timeout=10)
    resp.raise_for_status()


PRIORITY_MAP = {
    "it stopped working entirely": "urgent",
    "major degradation": "high",
    "minor issue, workaround exists": "normal",
    "general question": "low",
}


agent = guava.Agent(
    name="Alex",
    organization="Vantage Systems",
    purpose=(
        "to triage inbound support requests for Vantage Systems and trigger the "
        "right downstream workflow to get the customer helped quickly"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "fire_support_zap",
        objective=(
            "A customer is calling with a support issue. Collect their contact details, "
            "understand the problem, determine urgency, and trigger a Zapier workflow "
            "to create tickets in the appropriate systems."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Vantage Systems Support. My name is Alex. "
                "I'll collect some details so we can get your issue resolved as quickly "
                "as possible."
            ),
            guava.Field(
                key="caller_name",
                field_type="text",
                description="Ask for the caller's full name.",
                required=True,
            ),
            guava.Field(
                key="caller_email",
                field_type="text",
                description="Ask for their email address on file.",
                required=True,
            ),
            guava.Field(
                key="company",
                field_type="text",
                description="Ask what company they're with.",
                required=False,
            ),
            guava.Field(
                key="product_area",
                field_type="multiple_choice",
                description="Ask which part of our platform they're having trouble with.",
                choices=[
                    "login / account access",
                    "data sync / integrations",
                    "reporting / dashboards",
                    "mobile app",
                    "billing",
                    "API",
                    "other",
                ],
                required=True,
            ),
            guava.Field(
                key="issue_description",
                field_type="text",
                description=(
                    "Ask them to describe what's happening. What were they trying to do, "
                    "what went wrong, and are there any error messages? Capture all detail."
                ),
                required=True,
            ),
            guava.Field(
                key="impact_level",
                field_type="multiple_choice",
                description=(
                    "Ask how severely this is affecting their work right now."
                ),
                choices=[
                    "it stopped working entirely",
                    "major degradation",
                    "minor issue, workaround exists",
                    "general question",
                ],
                required=True,
            ),
        ],
    )


@agent.on_task_complete("fire_support_zap")
def on_done(call: guava.Call) -> None:
    name = call.get_field("caller_name") or "Unknown"
    email = call.get_field("caller_email") or ""
    company = call.get_field("company") or ""
    product_area = call.get_field("product_area") or "other"
    description = call.get_field("issue_description") or ""
    impact = call.get_field("impact_level") or "minor issue, workaround exists"

    priority = PRIORITY_MAP.get(impact, "normal")

    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "caller_name": name,
        "caller_email": email,
        "company": company,
        "product_area": product_area,
        "issue_description": description,
        "impact_level": impact,
        "priority": priority,
        "source": "guava_voice",
    }

    logging.info(
        "Triggering support intake Zap for %s — area: %s, priority: %s",
        name, product_area, priority,
    )

    try:
        trigger_zap(payload)
        logging.info("Support intake Zap triggered for %s.", name)

        sla_note = {
            "urgent": "Our on-call team will respond within 30 minutes.",
            "high": "A specialist will be in touch within 2 hours.",
            "normal": "Our support team will follow up within one business day.",
            "low": "You'll hear back within two business days.",
        }.get(priority, "Our team will be in touch soon.")

        call.hangup(
            final_instructions=(
                f"Let {name} know their support request has been submitted and prioritized as "
                f"{priority}. {sla_note} "
                "Thank them for reaching out to Vantage Systems and wish them a good day."
            )
        )
    except Exception as e:
        logging.error("Failed to trigger support Zap: %s", e)
        call.hangup(
            final_instructions=(
                f"Apologize to {name} for a technical issue and let them know their request has "
                "been noted. Ask them to email support@vantagesystems.com referencing "
                "the details they shared. Thank them for their patience."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
