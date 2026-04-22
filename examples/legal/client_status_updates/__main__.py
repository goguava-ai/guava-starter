import guava
import os
import logging
import json
import argparse
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)


class ClientStatusUpdateController(guava.CallController):
    def __init__(self, contact_name, matter_number, status_update, next_step):
        super().__init__()
        self.contact_name = contact_name
        self.matter_number = matter_number
        self.status_update = status_update
        self.next_step = next_step
        self.set_persona(
            organization_name="Hargrove & Associates Law Firm",
            agent_name="Morgan",
            agent_purpose=(
                "to proactively inform the client of the current status of their "
                "legal matter, confirm they understand the update and the next steps, "
                "and capture any questions they would like relayed to their attorney"
            ),
        )
        self.reach_person(
            contact_full_name=self.contact_name,
            on_success=self.begin_status_update,
            on_failure=self.recipient_unavailable,
        )

    def begin_status_update(self):
        self.set_task(
            objective=(
                f"Deliver a case status update to the client for matter number "
                f"{self.matter_number}. The current status is: {self.status_update}. "
                f"The next step is: {self.next_step}. Confirm the client understands "
                "both the update and the next step, capture any questions they have "
                "for their attorney, and note their preferred callback time if they "
                "would like to speak with someone directly."
            ),
            checklist=[
                guava.Say(
                    f"Good day. I am calling from Hargrove and Associates Law Firm "
                    f"with an update regarding matter number {self.matter_number}. "
                    f"Here is the current status: {self.status_update}. "
                    f"Regarding next steps: {self.next_step}. "
                    "I want to make sure you have all the information you need and "
                    "give you an opportunity to pass along any questions to your attorney."
                ),
                guava.Field(
                    key="update_understood",
                    description=(
                        "Confirmation that the client has heard and understood the "
                        "status update that was just provided"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="questions_for_attorney",
                    description=(
                        "Any questions the client would like relayed to their attorney, "
                        "noted verbatim where possible"
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="next_step_acknowledged",
                    description=(
                        "Confirmation that the client understands and acknowledges "
                        "the next step described in the update"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="preferred_callback_time",
                    description=(
                        "If the client would like to speak directly with their attorney "
                        "or a staff member, their preferred day and time for a callback"
                    ),
                    field_type="text",
                    required=False,
                ),
            ],
            on_complete=self.save_results,
        )

    def save_results(self):
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "call_type": "outbound_client_status_update",
            "meta": {
                "contact_name": self.contact_name,
                "matter_number": self.matter_number,
                "status_update": self.status_update,
                "next_step": self.next_step,
            },
            "fields": {
                "update_understood": self.get_field("update_understood"),
                "questions_for_attorney": self.get_field("questions_for_attorney"),
                "next_step_acknowledged": self.get_field("next_step_acknowledged"),
                "preferred_callback_time": self.get_field("preferred_callback_time"),
            },
        }
        print(json.dumps(results, indent=2))
        logging.info("Client status update results saved.")
        self.hangup(
            final_instructions=(
                "Thank the client by name for their time. If they provided questions "
                "for their attorney, assure them those will be passed along promptly. "
                "If they requested a callback, confirm that their preferred time has "
                "been noted. Remind them that Hargrove and Associates is committed to "
                "keeping them informed throughout their matter and that they are always "
                "welcome to contact the firm with questions. Say goodbye professionally."
            )
        )

    def recipient_unavailable(self):
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "call_type": "outbound_client_status_update",
            "status": "recipient_unavailable",
            "meta": {
                "contact_name": self.contact_name,
                "matter_number": self.matter_number,
                "status_update": self.status_update,
                "next_step": self.next_step,
            },
        }
        print(json.dumps(results, indent=2))
        logging.info("Recipient unavailable for status update call.")
        self.hangup(
            final_instructions=(
                "Leave a brief, professional voicemail identifying yourself as Morgan "
                "calling from Hargrove and Associates Law Firm. State that you are "
                f"calling with a status update on matter number {self.matter_number} "
                "and ask that they return your call at their earliest convenience or "
                "visit the client portal for the latest information. Provide the "
                "firm's main number and say goodbye."
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Outbound client status update call — Hargrove & Associates"
    )
    parser.add_argument("phone", help="Recipient phone number to dial")
    parser.add_argument("--name", required=True, help="Full name of the client")
    parser.add_argument("--matter-number", required=True, help="Matter or case number")
    parser.add_argument(
        "--status-update",
        required=True,
        help="Text describing the current status of the matter",
    )
    parser.add_argument(
        "--next-step",
        required=True,
        help="Text describing the next step or action in the matter",
    )
    args = parser.parse_args()

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=ClientStatusUpdateController(
            contact_name=args.name,
            matter_number=args.matter_number,
            status_update=args.status_update,
            next_step=args.next_step,
        ),
    )
