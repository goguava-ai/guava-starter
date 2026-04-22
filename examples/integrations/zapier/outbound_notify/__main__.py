import guava
import os
import logging
from guava import logging_utils
import argparse
import requests
from datetime import datetime, timezone


ZAPIER_WEBHOOK_URL = os.environ["ZAPIER_WEBHOOK_URL"]


def report_outcome(payload: dict) -> None:
    """POSTs the call outcome back to a Zapier Catch Hook for downstream logging."""
    resp = requests.post(ZAPIER_WEBHOOK_URL, json=payload, timeout=10)
    resp.raise_for_status()


class OutboundNotifyController(guava.CallController):
    def __init__(self, contact_name: str, message: str, campaign_id: str):
        super().__init__()
        self.contact_name = contact_name
        self.message = message
        self.campaign_id = campaign_id

        self.set_persona(
            organization_name="Clearpath",
            agent_name="Riley",
            agent_purpose=(
                "to deliver an important notification to Clearpath customers and confirm "
                "they received it"
            ),
        )

        self.reach_person(
            contact_full_name=contact_name,
            on_success=self.deliver_notification,
            on_failure=self.recipient_unavailable,
        )

    def deliver_notification(self):
        self.set_task(
            objective=(
                f"Deliver an important notification to {self.contact_name} and confirm "
                "they received and understood it."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.contact_name}, this is Riley calling from Clearpath. "
                    "I have an important update I'd like to share with you."
                ),
                guava.Say(self.message),
                guava.Field(
                    key="acknowledged",
                    field_type="multiple_choice",
                    description=(
                        "Ask the contact to confirm they understood the message. "
                        "Capture their acknowledgment."
                    ),
                    choices=["yes, understood", "has questions", "wants to opt out"],
                    required=True,
                ),
                guava.Field(
                    key="questions",
                    field_type="text",
                    description=(
                        "If they have questions, ask them to describe their question or concern. "
                        "Answer what you can; note what requires follow-up."
                    ),
                    required=False,
                ),
            ],
            on_complete=self.log_outcome,
        )

    def log_outcome(self):
        acknowledged = self.get_field("acknowledged") or "yes, understood"
        questions = self.get_field("questions") or ""

        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "campaign_id": self.campaign_id,
            "contact_name": self.contact_name,
            "outcome": acknowledged,
            "questions": questions,
            "call_status": "completed",
        }

        logging.info(
            "Notification delivered to %s — acknowledged: %s", self.contact_name, acknowledged,
        )

        try:
            report_outcome(payload)
            logging.info("Outcome reported to Zapier for campaign %s.", self.campaign_id)
        except Exception as e:
            logging.error("Failed to report outcome to Zapier: %s", e)

        if acknowledged == "wants to opt out":
            self.hangup(
                final_instructions=(
                    f"Acknowledge {self.contact_name}'s request to opt out. Let them know "
                    "they've been removed from future notifications. Thank them for letting "
                    "us know and wish them a good day."
                )
            )
        elif acknowledged == "has questions":
            self.hangup(
                final_instructions=(
                    f"Thank {self.contact_name} for their question. Let them know a team member "
                    "will follow up with a full answer within one business day. "
                    "Apologize if the message caused any confusion and wish them a great day."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Thank {self.contact_name} for their time. Let them know Clearpath is always "
                    "available if they have questions. Wish them a great day."
                )
            )

    def recipient_unavailable(self):
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "campaign_id": self.campaign_id,
            "contact_name": self.contact_name,
            "outcome": "unavailable",
            "questions": "",
            "call_status": "voicemail",
        }

        logging.info("Unable to reach %s — logging voicemail attempt.", self.contact_name)

        try:
            report_outcome(payload)
        except Exception as e:
            logging.error("Failed to report voicemail outcome to Zapier: %s", e)

        self.hangup(
            final_instructions=(
                f"Leave a brief, professional voicemail for {self.contact_name} from Clearpath. "
                "Summarize the key point of the notification message and ask them to call back "
                "or check their email for more details. Keep it under 30 seconds."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound notification call triggered by a Zapier workflow."
    )
    parser.add_argument("phone", help="Contact's phone number (E.164, e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Full name of the contact to reach")
    parser.add_argument("--message", required=True, help="The notification message to deliver")
    parser.add_argument("--campaign-id", required=True, help="Campaign ID for tracking in Zapier")
    args = parser.parse_args()

    logging.info(
        "Initiating notification call to %s (%s) — campaign: %s",
        args.name, args.phone, args.campaign_id,
    )

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=OutboundNotifyController(
            contact_name=args.name,
            message=args.message,
            campaign_id=args.campaign_id,
        ),
    )
