import guava
import os
import logging
from guava import logging_utils
import json
import argparse
from datetime import datetime, timezone



class DisruptionHandlingController(guava.CallController):
    def __init__(self, name, booking_reference, original_flight, disruption_reason):
        super().__init__()
        self.name = name
        self.booking_reference = booking_reference
        self.original_flight = original_flight
        self.disruption_reason = disruption_reason

        self.set_persona(
            organization_name="Meridian Travel Services",
            agent_name="Alex",
            agent_purpose=(
                "proactively contact a traveler affected by a flight or itinerary disruption, "
                "explain the situation clearly and calmly, understand their rebooking preferences, "
                "and confirm the best available alternative arrangements on their behalf"
            ),
        )

        self.reach_person(
            contact_full_name=self.name,
            on_success=self.begin_disruption_handling,
            on_failure=self.recipient_unavailable,
        )

    def begin_disruption_handling(self):
        self.set_task(
            objective=(
                f"You are calling {self.name} regarding a disruption to their itinerary. "
                f"Booking reference: {self.booking_reference}. "
                f"Affected flight: {self.original_flight}. "
                f"Reason for disruption: {self.disruption_reason}. "
                "Begin by acknowledging the inconvenience with sincere empathy. Clearly explain "
                "the disruption, then work collaboratively with the traveler to understand their "
                "rebooking preferences — whether they want the next available option, a specific "
                "alternative date, or a refund. Collect any relevant seat and meal preferences to "
                "ensure their new arrangements are as comfortable as possible. End by capturing "
                "their email address so confirmation details can be sent promptly."
            ),
            checklist=[
                guava.Say(
                    f"Greet {self.name} and acknowledge the disruption to their upcoming travel. "
                    f"Briefly explain that flight {self.original_flight} has been affected by "
                    f"{self.disruption_reason}, and express genuine apology for the inconvenience. "
                    "Reassure them that you are here to resolve this as smoothly as possible."
                ),
                guava.Field(
                    key="disruption_acknowledged",
                    description=(
                        "Has the traveler acknowledged the disruption notification and confirmed "
                        "they understand the situation?"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="rebooking_preference",
                    description=(
                        "What is the traveler's preferred resolution? Options include: "
                        "next_available flight, a specific_date of their choosing, or a full refund."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="preferred_departure_date",
                    description=(
                        "If the traveler would like to rebook on a specific date, "
                        "what date do they prefer for their new departure?"
                    ),
                    field_type="date",
                    required=False,
                ),
                guava.Field(
                    key="seat_preference",
                    description=(
                        "Does the traveler have a seat preference for their rebooked flight, "
                        "such as window, aisle, exit row, or business class?"
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="meal_preference",
                    description=(
                        "Does the traveler have a meal preference or dietary requirement "
                        "for their rebooked flight?"
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="contact_email_for_confirmation",
                    description=(
                        "What email address should the new booking confirmation and itinerary "
                        "details be sent to?"
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
            "use_case": "disruption_handling",
            "traveler_name": self.name,
            "booking_reference": self.booking_reference,
            "original_flight": self.original_flight,
            "disruption_reason": self.disruption_reason,
            "fields": {
                "disruption_acknowledged": self.get_field("disruption_acknowledged"),
                "rebooking_preference": self.get_field("rebooking_preference"),
                "preferred_departure_date": self.get_field("preferred_departure_date"),
                "seat_preference": self.get_field("seat_preference"),
                "meal_preference": self.get_field("meal_preference"),
                "contact_email_for_confirmation": self.get_field("contact_email_for_confirmation"),
            },
        }
        print(json.dumps(results, indent=2))
        logging.info("Disruption handling results saved for %s", self.name)
        self.hangup(
            final_instructions=(
                f"Thank {self.name} for their patience and understanding during what is clearly "
                "an inconvenient situation. Confirm that a member of the Meridian Travel Services "
                "team will process their preferred resolution and send full confirmation details "
                "to the email provided. If they requested rebooking, let them know the new itinerary "
                "will be issued as quickly as possible. Close with warmth and confidence, reassuring "
                "them they are in good hands."
            )
        )

    def recipient_unavailable(self):
        logging.warning("Could not reach %s for disruption handling call.", self.name)
        self.hangup(
            final_instructions=(
                "Leave an urgent but calm voicemail as Alex from Meridian Travel Services, "
                "informing the traveler of the disruption to their upcoming flight and asking them "
                "to call back as soon as possible so the team can arrange an alternative. "
                "Provide a sense of urgency without causing alarm, and assure them that the team "
                "is standing by to assist."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound flight disruption handling call — Meridian Travel Services"
    )
    parser.add_argument("phone", help="Traveler phone number to call")
    parser.add_argument("--name", required=True, help="Full name of the traveler")
    parser.add_argument("--booking-reference", required=True, help="Booking reference number")
    parser.add_argument("--original-flight", required=True, help="Affected flight number or identifier")
    parser.add_argument(
        "--disruption-reason",
        default="an operational change",
        help="Reason for the disruption (default: an operational change)",
    )
    args = parser.parse_args()

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=DisruptionHandlingController(
            name=args.name,
            booking_reference=args.booking_reference,
            original_flight=args.original_flight,
            disruption_reason=args.disruption_reason,
        ),
    )
