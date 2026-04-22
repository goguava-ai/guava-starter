import guava
import os
import logging
import json
import argparse
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)


class SchedulingController(guava.CallController):
    def __init__(self, contact_name, matter_number, event_type, proposed_date):
        super().__init__()
        self.contact_name = contact_name
        self.matter_number = matter_number
        self.event_type = event_type
        self.proposed_date = proposed_date
        self.set_persona(
            organization_name="Hargrove & Associates Law Firm",
            agent_name="Riley",
            agent_purpose=(
                "to coordinate scheduling for a legal proceeding and confirm the "
                "availability, preferred logistics, and contact details of the party "
                "being reached"
            ),
        )
        self.reach_person(
            contact_full_name=self.contact_name,
            on_success=self.begin_scheduling,
            on_failure=self.recipient_unavailable,
        )

    def begin_scheduling(self):
        self.set_task(
            objective=(
                f"Confirm scheduling details for an upcoming {self.event_type} related "
                f"to matter number {self.matter_number}. The firm has proposed "
                f"{self.proposed_date} as a potential date. Verify the party's "
                "availability, collect their preferences, and obtain a confirmation "
                "email address. Remain professional and courteous throughout."
            ),
            checklist=[
                guava.Say(
                    f"Good day. I am calling on behalf of Hargrove and Associates Law "
                    f"Firm regarding the scheduling of an upcoming {self.event_type} "
                    f"for matter number {self.matter_number}. The firm has proposed "
                    f"{self.proposed_date} as a potential date, and I would like to "
                    "confirm your availability and preferred arrangements."
                ),
                guava.Field(
                    key="availability_confirmed",
                    description=(
                        f"Whether the party is available on or around the proposed date "
                        f"of {self.proposed_date} for the {self.event_type}"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="preferred_date",
                    description=(
                        f"The party's preferred date for the {self.event_type}, "
                        f"if different from the proposed date of {self.proposed_date}"
                    ),
                    field_type="date",
                    required=True,
                ),
                guava.Field(
                    key="preferred_time",
                    description=(
                        f"The party's preferred time of day for the {self.event_type}, "
                        "such as morning, afternoon, or a specific hour"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="location_preference",
                    description=(
                        f"How the party would prefer to participate in the "
                        f"{self.event_type}: in person, by video conference, or by phone"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="special_accommodations",
                    description=(
                        "Any special accommodations or requirements the party needs, "
                        "such as accessibility needs, an interpreter, or technical "
                        "requirements for video participation"
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="confirmation_email",
                    description=(
                        "The email address where the party would like to receive the "
                        "formal scheduling confirmation and any related documents"
                    ),
                    field_type="text",
                    required=True,
                ),
            ],
            on_complete=self.save_results,
        )

    def save_results(self):
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "call_type": "outbound_scheduling",
            "meta": {
                "contact_name": self.contact_name,
                "matter_number": self.matter_number,
                "event_type": self.event_type,
                "proposed_date": self.proposed_date,
            },
            "fields": {
                "availability_confirmed": self.get_field("availability_confirmed"),
                "preferred_date": self.get_field("preferred_date"),
                "preferred_time": self.get_field("preferred_time"),
                "location_preference": self.get_field("location_preference"),
                "special_accommodations": self.get_field("special_accommodations"),
                "confirmation_email": self.get_field("confirmation_email"),
            },
        }
        print(json.dumps(results, indent=2))
        logging.info("Scheduling results saved.")
        self.hangup(
            final_instructions=(
                "Thank the party by name for their time and cooperation. Confirm that "
                "the scheduling details have been recorded and that they will receive a "
                "formal confirmation at the email address they provided. Let them know "
                "that if anything changes or they have questions, they are welcome to "
                "contact Hargrove and Associates directly. Say goodbye professionally."
            )
        )

    def recipient_unavailable(self):
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "call_type": "outbound_scheduling",
            "status": "recipient_unavailable",
            "meta": {
                "contact_name": self.contact_name,
                "matter_number": self.matter_number,
                "event_type": self.event_type,
                "proposed_date": self.proposed_date,
            },
        }
        print(json.dumps(results, indent=2))
        logging.info("Recipient unavailable for scheduling call.")
        self.hangup(
            final_instructions=(
                "Leave a brief, professional voicemail identifying yourself as Riley "
                "calling from Hargrove and Associates Law Firm. State that you are "
                f"calling regarding the scheduling of an upcoming {self.event_type} "
                f"for matter number {self.matter_number} and that you would appreciate "
                "a call back at their earliest convenience. Provide the firm's main "
                "number and say goodbye."
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Outbound scheduling coordination call — Hargrove & Associates"
    )
    parser.add_argument("phone", help="Recipient phone number to dial")
    parser.add_argument("--name", required=True, help="Full name of the contact")
    parser.add_argument("--matter-number", required=True, help="Matter or case number")
    parser.add_argument(
        "--event-type",
        default="deposition",
        help="Type of legal event being scheduled (default: deposition)",
    )
    parser.add_argument(
        "--proposed-date", required=True, help="Proposed date for the event"
    )
    args = parser.parse_args()

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=SchedulingController(
            contact_name=args.name,
            matter_number=args.matter_number,
            event_type=args.event_type,
            proposed_date=args.proposed_date,
        ),
    )
