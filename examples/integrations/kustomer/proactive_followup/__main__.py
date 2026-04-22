import guava
import os
import logging
from guava import logging_utils
import argparse
import requests
from datetime import datetime, timezone


TOKEN = os.environ["KUSTOMER_API_TOKEN"]
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
BASE_URL = "https://api.kustomerapp.com/v1"


def get_conversation(conversation_id: str) -> dict | None:
    """Fetches a single conversation by ID. Returns the conversation object or None."""
    resp = requests.get(
        f"{BASE_URL}/conversations/{conversation_id}",
        headers=HEADERS,
        timeout=10,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    data = resp.json().get("data")
    return data if data else None


def close_conversation(conversation_id: str) -> dict:
    """Sets a conversation status to done. Returns the updated conversation object."""
    payload = {"status": "done"}
    resp = requests.patch(
        f"{BASE_URL}/conversations/{conversation_id}",
        headers=HEADERS,
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["data"]


def add_note(conversation_id: str, body: str) -> dict:
    """Posts an internal note to a conversation. Returns the note object."""
    payload = {"body": body}
    resp = requests.post(
        f"{BASE_URL}/conversations/{conversation_id}/notes",
        headers=HEADERS,
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["data"]


class ProactiveFollowupController(guava.CallController):
    def __init__(self, conv_id: str, customer_name: str):
        super().__init__()
        self.conv_id = conv_id
        self.customer_name = customer_name
        self.issue_summary = "your open support case"
        self.conv_status = "open"

        # Pre-call: fetch the conversation to get context for the follow-up.
        try:
            conversation = get_conversation(conv_id)
            if conversation:
                attrs = conversation.get("attributes", {})
                self.conv_status = attrs.get("status", "open")
                preview = attrs.get("preview") or attrs.get("subject") or ""
                if preview:
                    self.issue_summary = f"'{preview}'"
        except Exception as e:
            logging.error("Failed to fetch conversation %s pre-call: %s", conv_id, e)

        self.set_persona(
            organization_name="Brightpath Support",
            agent_name="Taylor",
            agent_purpose=(
                "to proactively follow up with customers on open support cases that haven't "
                "been updated recently on behalf of Brightpath Support"
            ),
        )

        self.reach_person(
            contact_full_name=self.customer_name,
            on_success=self.begin_followup,
            on_failure=self.recipient_unavailable,
        )

    def begin_followup(self):
        self.set_task(
            objective=(
                f"Follow up with {self.customer_name} on their open support case "
                f"{self.issue_summary} to check whether the issue has been resolved and "
                "determine the best next step."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.customer_name}, this is Taylor calling from Brightpath Support. "
                    f"I'm reaching out to follow up on your open support case regarding "
                    f"{self.issue_summary}. We noticed it hasn't had any recent updates and "
                    "wanted to check in with you."
                ),
                guava.Field(
                    key="issue_resolved",
                    field_type="multiple_choice",
                    description=(
                        "Ask whether their issue has been resolved. "
                        "Capture: yes (fully resolved), partially (still some problems), "
                        "or no (issue is still ongoing)."
                    ),
                    choices=["yes", "partially", "no"],
                    required=True,
                ),
                guava.Field(
                    key="additional_help_needed",
                    field_type="text",
                    description=(
                        "Ask if there is any additional information or help they'd like to provide "
                        "or request regarding this case. Capture their response, or 'none' if they "
                        "have nothing to add."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="preferred_followup",
                    field_type="multiple_choice",
                    description=(
                        "Ask how they'd prefer we handle this case going forward: "
                        "send a follow-up by email, schedule a callback with a support agent, "
                        "or close the case."
                    ),
                    choices=["email", "callback", "close-case"],
                    required=True,
                ),
            ],
            on_complete=self.handle_outcome,
        )

    def handle_outcome(self):
        issue_resolved = self.get_field("issue_resolved") or "no"
        additional_help = self.get_field("additional_help_needed") or ""
        preferred_followup = self.get_field("preferred_followup") or "email"

        logging.info(
            "Follow-up outcome for conversation %s — resolved: %s, preferred: %s",
            self.conv_id, issue_resolved, preferred_followup,
        )

        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        note_lines = [
            f"Proactive follow-up call — {timestamp}",
            f"Customer: {self.customer_name}",
            f"Issue resolved: {issue_resolved}",
            f"Preferred next step: {preferred_followup}",
        ]
        if additional_help and additional_help.strip().lower() not in ("none", "n/a", ""):
            note_lines.append(f"Additional information: {additional_help}")

        if preferred_followup == "close-case":
            # Close the conversation and add a closing note
            try:
                close_conversation(self.conv_id)
                logging.info("Closed conversation %s per customer request", self.conv_id)
            except Exception as e:
                logging.error("Failed to close conversation %s: %s", self.conv_id, e)

            note_lines.append("Case closed per customer request during follow-up call.")
            try:
                add_note(self.conv_id, "\n".join(note_lines))
            except Exception as e:
                logging.error("Failed to add closing note to conversation %s: %s", self.conv_id, e)

            self.hangup(
                final_instructions=(
                    f"Let {self.customer_name} know their support case has been closed. "
                    "Remind them they can always call back or reach out by email if the issue "
                    "recurs or if they need any further assistance. "
                    "Thank them for being a Brightpath Support customer."
                )
            )
        else:
            # Leave the conversation open and record a follow-up note
            try:
                add_note(self.conv_id, "\n".join(note_lines))
                logging.info("Follow-up note added to conversation %s", self.conv_id)
            except Exception as e:
                logging.error(
                    "Failed to add follow-up note to conversation %s: %s", self.conv_id, e
                )

            if preferred_followup == "callback":
                self.hangup(
                    final_instructions=(
                        f"Let {self.customer_name} know that a support agent will call them back "
                        "within one business day to continue working on their case. "
                        "Thank them for their patience and for being a Brightpath Support customer."
                    )
                )
            else:
                self.hangup(
                    final_instructions=(
                        f"Let {self.customer_name} know that our support team will send them an "
                        "email with an update shortly. "
                        "Thank them for their patience and for being a Brightpath Support customer."
                    )
                )

    def recipient_unavailable(self):
        logging.info(
            "Unable to reach %s for follow-up on conversation %s",
            self.customer_name, self.conv_id,
        )

        # Leave a note that a follow-up was attempted
        try:
            note = (
                f"Proactive follow-up call attempted — "
                f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n"
                f"Customer: {self.customer_name}\n"
                "Outcome: Customer not available — voicemail left."
            )
            add_note(self.conv_id, note)
        except Exception as e:
            logging.error("Failed to add follow-up attempt note to conversation %s: %s", self.conv_id, e)

        self.hangup(
            final_instructions=(
                f"Leave a brief, friendly voicemail for {self.customer_name} on behalf of "
                "Brightpath Support. Let them know you were calling to follow up on their open "
                f"support case regarding {self.issue_summary}. Ask them to call back at their "
                "convenience or reply to their case email if they have any updates. "
                "Let them know our team is here to help."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound proactive follow-up call for an open Kustomer conversation."
    )
    parser.add_argument("phone", help="Customer phone number to call (E.164 format, e.g. +15551234567)")
    parser.add_argument("--conv-id", required=True, help="Kustomer conversation ID")
    parser.add_argument("--name", required=True, help="Customer's full name")
    args = parser.parse_args()

    logging.info(
        "Initiating proactive follow-up call to %s (%s) for conversation %s",
        args.name, args.phone, args.conv_id,
    )

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=ProactiveFollowupController(
            conv_id=args.conv_id,
            customer_name=args.name,
        ),
    )
