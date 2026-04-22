import guava
import os
import logging
from guava import logging_utils
import json
import argparse
from datetime import datetime, timezone



class PreArrivalController(guava.CallController):
    def __init__(self, name, reservation_number, checkin_date):
        super().__init__()
        self.name = name
        self.reservation_number = reservation_number
        self.checkin_date = checkin_date

        self.set_persona(
            organization_name="The Grand Meridian Hotel",
            agent_name="Sophie",
            agent_purpose=(
                "reach out to a guest ahead of their arrival to ensure every detail of their "
                "stay is thoughtfully prepared, including dietary needs, accessibility requirements, "
                "room preferences, and any special requests"
            ),
        )

        self.reach_person(
            contact_full_name=self.name,
            on_success=self.begin_pre_arrival,
            on_failure=self.recipient_unavailable,
        )

    def begin_pre_arrival(self):
        self.set_task(
            objective=(
                f"You are calling {self.name} ahead of their check-in on {self.checkin_date} "
                f"(reservation {self.reservation_number}). Your goal is to ensure the hotel team "
                "has everything needed to personalise their stay. Ask about dietary restrictions, "
                "accessibility requirements, room and pillow preferences, estimated arrival time, "
                "and any other special requests. Approach the conversation with warmth and genuine "
                "care, making the guest feel valued and well looked after before they even arrive."
            ),
            checklist=[
                guava.Say(
                    f"Greet {self.name} warmly, introduce yourself, and let them know you are "
                    f"calling to help personalise their upcoming stay arriving on {self.checkin_date}."
                ),
                guava.Field(
                    key="dietary_restrictions",
                    description=(
                        "Does the guest have any dietary restrictions, allergies, or food preferences "
                        "the hotel should be aware of?"
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="accessibility_needs",
                    description=(
                        "Does the guest require any accessibility accommodations, such as a "
                        "roll-in shower, grab bars, wheelchair-accessible room, or other assistance?"
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="bed_preference",
                    description=(
                        "Does the guest have a bed configuration preference, "
                        "such as a king bed or two queen beds?"
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="pillow_preference",
                    description=(
                        "Does the guest have a pillow preference, such as firm, soft, "
                        "down, or hypoallergenic pillows?"
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="estimated_arrival_time",
                    description="What time does the guest expect to arrive at the hotel?",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="special_requests",
                    description=(
                        "Are there any other special requests or personal touches the guest "
                        "would like arranged before or during their stay?"
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
            "use_case": "pre_arrival",
            "guest_name": self.name,
            "reservation_number": self.reservation_number,
            "checkin_date": self.checkin_date,
            "fields": {
                "dietary_restrictions": self.get_field("dietary_restrictions"),
                "accessibility_needs": self.get_field("accessibility_needs"),
                "bed_preference": self.get_field("bed_preference"),
                "pillow_preference": self.get_field("pillow_preference"),
                "estimated_arrival_time": self.get_field("estimated_arrival_time"),
                "special_requests": self.get_field("special_requests"),
            },
        }
        print(json.dumps(results, indent=2))
        logging.info("Pre-arrival preferences saved for %s", self.name)
        self.hangup(
            final_instructions=(
                f"Thank {self.name} graciously for taking the time to share their preferences. "
                "Let them know the hotel team will have everything ready upon arrival, and express "
                "how much the team is looking forward to welcoming them. Wish them a pleasant journey."
            )
        )

    def recipient_unavailable(self):
        logging.warning("Could not reach %s for pre-arrival call.", self.name)
        self.hangup(
            final_instructions=(
                "Leave a warm and professional voicemail as Sophie from The Grand Meridian Hotel, "
                "mentioning that you are calling ahead of their upcoming stay to ensure everything "
                "is perfectly prepared. Invite them to call back or contact the concierge team "
                "with any preferences or special requests."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound pre-arrival preferences call — The Grand Meridian Hotel"
    )
    parser.add_argument("phone", help="Guest phone number to call")
    parser.add_argument("--name", required=True, help="Full name of the guest")
    parser.add_argument("--reservation-number", required=True, help="Reservation reference number")
    parser.add_argument("--checkin-date", required=True, help="Scheduled check-in date")
    args = parser.parse_args()

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=PreArrivalController(
            name=args.name,
            reservation_number=args.reservation_number,
            checkin_date=args.checkin_date,
        ),
    )
