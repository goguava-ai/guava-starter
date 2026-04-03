import guava
import os
import logging
import requests
from datetime import datetime

logging.basicConfig(level=logging.INFO)

ZAPIER_WEBHOOK_URL = os.environ["ZAPIER_WEBHOOK_URL"]


def trigger_zap(payload: dict) -> None:
    """POSTs the payload to the Zapier Catch Hook URL to trigger the Zap."""
    resp = requests.post(ZAPIER_WEBHOOK_URL, json=payload, timeout=10)
    resp.raise_for_status()


class WebhookTriggerController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Brightline Services",
            agent_name="Taylor",
            agent_purpose=(
                "to collect information from callers and route it automatically "
                "to the right team via Brightline's workflow automation"
            ),
        )

        self.set_task(
            objective=(
                "A caller has reached Brightline Services. Greet them, understand their request, "
                "collect the necessary details, and trigger an automated workflow to route their "
                "inquiry to the right team."
            ),
            checklist=[
                guava.Say(
                    "Thank you for calling Brightline Services. I'm Taylor. "
                    "I'll collect a few details and make sure your request gets to the right team."
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
                    description="Ask for their email address.",
                    required=True,
                ),
                guava.Field(
                    key="request_type",
                    field_type="multiple_choice",
                    description="Ask what brings them in today.",
                    choices=[
                        "new customer inquiry",
                        "existing customer support",
                        "billing question",
                        "partnership interest",
                        "other",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="request_detail",
                    field_type="text",
                    description=(
                        "Ask them to briefly describe their request or question. "
                        "Capture a clear summary."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="preferred_contact",
                    field_type="multiple_choice",
                    description="Ask how they'd prefer to be followed up with.",
                    choices=["email", "phone call", "either"],
                    required=True,
                ),
            ],
            on_complete=self.fire_webhook,
        )

        self.accept_call()

    def fire_webhook(self):
        name = self.get_field("caller_name") or "Unknown"
        email = self.get_field("caller_email") or ""
        request_type = self.get_field("request_type") or "other"
        detail = self.get_field("request_detail") or ""
        contact_pref = self.get_field("preferred_contact") or "email"

        payload = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "caller_name": name,
            "caller_email": email,
            "request_type": request_type,
            "request_detail": detail,
            "preferred_contact": contact_pref,
            "source": "guava_voice",
        }

        logging.info("Triggering Zap for %s — request type: %s", name, request_type)
        try:
            trigger_zap(payload)
            logging.info("Zapier webhook triggered successfully.")
            self.hangup(
                final_instructions=(
                    f"Let {name} know their request has been received and routed to the right team. "
                    f"They'll be contacted via {contact_pref} within one business day. "
                    "Thank them for calling Brightline Services and wish them a great day."
                )
            )
        except Exception as e:
            logging.error("Failed to trigger Zapier webhook: %s", e)
            self.hangup(
                final_instructions=(
                    f"Apologize to {name} for a brief technical hiccup. Let them know their request "
                    "has been noted and someone will follow up shortly. Thank them for their patience."
                )
            )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=WebhookTriggerController,
    )
