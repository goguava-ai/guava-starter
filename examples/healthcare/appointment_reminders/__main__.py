import guava
import os
import logging
import json
import argparse
from datetime import datetime

logging.basicConfig(level=logging.INFO)


class AppointmentReminderController(guava.CallController):
    def __init__(self, patient_name: str, appointment: str):
        super().__init__()
        self.patient_name = patient_name
        self.appointment = appointment

        self.set_persona(
            organization_name="Bright Smile Dental",
            agent_name="Jordan",
            agent_purpose=(
                "to remind patients of their upcoming dental appointments, "
                "confirm attendance, and assist with rescheduling if needed"
            ),
        )

        self.reach_person(
            contact_full_name=self.patient_name,
            on_success=self.begin_reminder,
            on_failure=self.recipient_unavailable,
        )

    def begin_reminder(self):
        self.set_task(
            objective=(
                f"Remind {self.patient_name} of their dental appointment at Bright Smile Dental "
                f"scheduled for {self.appointment}. Confirm whether they will attend or need to "
                "reschedule. If rescheduling is needed, collect their preferred day and time. "
                "Be friendly, professional, and concise."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.patient_name}, this is Jordan calling from Bright Smile Dental. "
                    f"I'm reaching out to confirm your upcoming appointment scheduled for {self.appointment}."
                ),
                guava.Say(
                    "We want to make sure we have you on the schedule and that the time still works for you."
                ),
                guava.Field(
                    key="appointment_confirmed",
                    description=(
                        "Ask the patient whether they confirm their appointment or need to reschedule. "
                        "Acceptable responses: 'confirm' or 'reschedule'."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="reschedule_requested",
                    description=(
                        "If the patient wants to reschedule, ask for their preferred day and time "
                        "for the new appointment. Only collect this if they said they need to reschedule."
                    ),
                    field_type="text",
                    required=False,
                ),
            ],
            on_complete=self.save_results,
        )

    def save_results(self):
        results = {
            "timestamp": datetime.now().isoformat(),
            "patient_name": self.patient_name,
            "appointment": self.appointment,
            "appointment_confirmed": self.get_field("appointment_confirmed"),
            "reschedule_requested": self.get_field("reschedule_requested"),
        }
        print(json.dumps(results, indent=2))
        logging.info("Appointment reminder results saved.")

        confirmed = self.get_field("appointment_confirmed")
        if confirmed and confirmed.strip().lower() == "reschedule":
            self.hangup(
                final_instructions=(
                    "Thank the patient for letting us know. Let them know that a team member from "
                    "Bright Smile Dental will follow up shortly to confirm a new appointment time. "
                    "Wish them a great day."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    "Thank the patient for confirming their appointment. Remind them to arrive "
                    "10 minutes early to complete any necessary paperwork, and let them know we "
                    "look forward to seeing them. Wish them a great day."
                )
            )

    def recipient_unavailable(self):
        self.hangup(
            final_instructions=(
                "We were unable to reach the patient. Leave a brief, friendly voicemail on behalf "
                "of Bright Smile Dental asking them to call back to confirm or reschedule their "
                f"appointment on {self.appointment}. Provide the office number if available."
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Outbound appointment reminder call for Bright Smile Dental."
    )
    parser.add_argument("phone", help="Patient phone number to call")
    parser.add_argument("--name", required=True, help="Full name of the patient")
    parser.add_argument(
        "--appointment",
        default="tomorrow at 2:00 PM",
        help="Appointment datetime string (default: 'tomorrow at 2:00 PM')",
    )
    args = parser.parse_args()

    logging.info(
        "Initiating appointment reminder call to %s (%s) for appointment: %s",
        args.name,
        args.phone,
        args.appointment,
    )

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=AppointmentReminderController(
            patient_name=args.name,
            appointment=args.appointment,
        ),
    )
