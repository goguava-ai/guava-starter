import guava
import os
import logging
import json
import argparse
from datetime import datetime

logging.basicConfig(level=logging.INFO)


class PatientIntakeController(guava.CallController):
    def __init__(self, patient_name: str, appointment: str):
        super().__init__()
        self.patient_name = patient_name
        self.appointment = appointment

        self.set_persona(
            organization_name="Summit Health Clinic",
            agent_name="Morgan",
            agent_purpose=(
                "to conduct pre-visit intake calls to collect patient symptoms, current medications, "
                "allergies, insurance information, and emergency contact details before their appointment"
            ),
        )

        self.reach_person(
            contact_full_name=self.patient_name,
            on_success=self.begin_intake,
            on_failure=self.recipient_unavailable,
        )

    def begin_intake(self):
        self.set_task(
            objective=(
                f"Complete a pre-visit intake for {self.patient_name} ahead of {self.appointment} "
                "at Summit Health Clinic. Collect the patient's primary reason for the visit, "
                "current medications, any known allergies, insurance provider and member ID, "
                "and emergency contact information. Be warm, patient, and professional — this "
                "information will help the care team be fully prepared before the patient arrives."
            ),
            checklist=[
                guava.Say(
                    f"Hello {self.patient_name}, this is Morgan calling from Summit Health Clinic. "
                    f"I'm calling ahead of {self.appointment} to complete a quick intake so our care "
                    "team is fully prepared for your visit. This should only take a few minutes."
                ),
                guava.Say(
                    "Everything you share will be kept confidential and used only to support your care."
                ),
                guava.Field(
                    key="chief_complaint",
                    description=(
                        "Ask the patient to describe their primary reason for visiting Summit Health Clinic. "
                        "What symptoms, concerns, or conditions are they hoping to address at this appointment?"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="current_medications",
                    description=(
                        "Ask if the patient is currently taking any medications, including prescription drugs, "
                        "over-the-counter medications, vitamins, or supplements. Capture the list as described. "
                        "If none, that is acceptable to leave blank."
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="known_allergies",
                    description=(
                        "Ask if the patient has any known allergies, particularly to medications, foods, latex, "
                        "or environmental factors. Capture any allergies they mention. "
                        "If none, that is acceptable to leave blank."
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="insurance_provider",
                    description=(
                        "Ask the patient for the name of their health insurance provider "
                        "(e.g., 'Blue Cross Blue Shield', 'Aetna', 'United Healthcare')."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="insurance_member_id",
                    description=(
                        "Ask the patient for their insurance member ID number, which can be found on their "
                        "insurance card. Capture the full ID exactly as they provide it."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="emergency_contact_name",
                    description=(
                        "Ask the patient for the full name of their emergency contact — someone we can reach "
                        "if needed during or after their visit."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="emergency_contact_phone",
                    description=(
                        "Ask the patient for the phone number of their emergency contact."
                    ),
                    field_type="text",
                    required=True,
                ),
            ],
            on_complete=self.save_results,
        )

    def save_results(self):
        results = {
            "timestamp": datetime.now().isoformat(),
            "patient_name": self.patient_name,
            "appointment": self.appointment,
            "chief_complaint": self.get_field("chief_complaint"),
            "current_medications": self.get_field("current_medications"),
            "known_allergies": self.get_field("known_allergies"),
            "insurance_provider": self.get_field("insurance_provider"),
            "insurance_member_id": self.get_field("insurance_member_id"),
            "emergency_contact_name": self.get_field("emergency_contact_name"),
            "emergency_contact_phone": self.get_field("emergency_contact_phone"),
        }
        print(json.dumps(results, indent=2))
        logging.info("Patient intake results saved.")

        self.hangup(
            final_instructions=(
                f"Thank {self.patient_name} for completing the intake. Let them know their information "
                "has been securely recorded and will be reviewed by the care team at Summit Health Clinic "
                f"before {self.appointment}. Remind them to bring their insurance card and a photo ID to "
                "the appointment, and to arrive 10 minutes early. Wish them a great visit."
            )
        )

    def recipient_unavailable(self):
        self.hangup(
            final_instructions=(
                "We were unable to reach the patient. Leave a brief, friendly voicemail on behalf of "
                "Summit Health Clinic letting them know we called to complete a pre-visit intake ahead "
                f"of {self.appointment} and asking them to call us back at their earliest convenience. "
                "Let them know this will only take a few minutes and will help us prepare for their visit."
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Outbound pre-visit patient intake call for Summit Health Clinic."
    )
    parser.add_argument("phone", help="Patient phone number to call")
    parser.add_argument("--name", required=True, help="Full name of the patient")
    parser.add_argument(
        "--appointment",
        default="your upcoming appointment",
        help="Appointment time description (default: 'your upcoming appointment')",
    )
    args = parser.parse_args()

    logging.info(
        "Initiating patient intake call to %s (%s) for appointment: %s",
        args.name,
        args.phone,
        args.appointment,
    )

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=PatientIntakeController(
            patient_name=args.name,
            appointment=args.appointment,
        ),
    )
