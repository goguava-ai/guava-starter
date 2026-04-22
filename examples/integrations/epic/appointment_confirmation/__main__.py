import guava
import os
import logging
from guava import logging_utils
import json
import requests
import argparse
from datetime import datetime, timezone



class AppointmentConfirmationController(guava.CallController):
    def __init__(self, patient_name: str, appointment_id: str):
        super().__init__()
        self.patient_name = patient_name
        self.appointment_id = appointment_id
        self.appointment_display = "your upcoming appointment"

        # Pre-call: fetch the appointment from Epic so the agent can speak the exact
        # date and time.
        try:
            base_url = os.environ["EPIC_BASE_URL"]
            access_token = os.environ["EPIC_ACCESS_TOKEN"]
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }
            resp = requests.get(
                f"{base_url}/Appointment/{appointment_id}",
                headers=headers,
                timeout=10,
            )
            resp.raise_for_status()
            appt = resp.json()
            start = appt.get("start", "")
            if start:
                # Format the ISO timestamp into a natural-language string for the agent to speak
                dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
                self.appointment_display = dt.strftime("%A, %B %-d at %-I:%M %p")
        except Exception as e:
            logging.error("Failed to fetch Epic Appointment: %s", e)

        self.set_persona(
            organization_name="Cedar Health",
            agent_name="Maya",
            agent_purpose=(
                "to confirm or cancel upcoming appointments on behalf of Cedar Health "
                "and update the appointment record in Epic accordingly"
            ),
        )

        self.reach_person(
            contact_full_name=self.patient_name,
            on_success=self.begin_confirmation,
            on_failure=self.recipient_unavailable,
        )

    def begin_confirmation(self):
        self.set_task(
            objective=(
                f"Confirm or cancel {self.patient_name}'s appointment at Cedar Health "
                f"scheduled for {self.appointment_display}. Be warm, concise, and respectful."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.patient_name}, this is Maya calling from Cedar Health. "
                    f"I'm reaching out to confirm your appointment scheduled for {self.appointment_display}."
                ),
                guava.Field(
                    key="confirmation",
                    description=(
                        "Ask whether the patient will keep their appointment or needs to cancel. "
                        "Capture 'confirm' or 'cancel'."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="cancellation_reason",
                    description=(
                        "If the patient wants to cancel, ask for the reason. "
                        "Only collect this if they said they need to cancel."
                    ),
                    field_type="text",
                    required=False,
                ),
            ],
            on_complete=self.save_results,
        )

    def save_results(self):
        confirmation = self.get_field("confirmation")
        cancellation_reason = self.get_field("cancellation_reason")

        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": "Maya",
            "organization": "Cedar Health",
            "use_case": "appointment_confirmation",
            "patient_name": self.patient_name,
            "appointment_id": self.appointment_id,
            "fields": {
                "confirmation": confirmation,
                "cancellation_reason": cancellation_reason,
            },
        }
        print(json.dumps(results, indent=2))
        logging.info("Appointment confirmation results saved locally.")

        # Post-call: patch the appointment status in Epic based on the patient's choice.
        # PATCH rather than PUT so we only touch the status field without overwriting
        # other appointment data. Cancellation reason is included in comment when provided.
        try:
            base_url = os.environ["EPIC_BASE_URL"]
            access_token = os.environ["EPIC_ACCESS_TOKEN"]
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }

            cancelled = confirmation and confirmation.strip().lower() == "cancel"
            new_status = "cancelled" if cancelled else "booked"

            patch_payload = {"resourceType": "Appointment", "id": self.appointment_id, "status": new_status}
            if cancelled and cancellation_reason:
                patch_payload["comment"] = f"Patient cancellation reason: {cancellation_reason}"

            resp = requests.patch(
                f"{base_url}/Appointment/{self.appointment_id}",
                headers=headers,
                json=patch_payload,
                timeout=10,
            )
            resp.raise_for_status()
            logging.info("Epic Appointment %s updated to status: %s", self.appointment_id, new_status)
        except Exception as e:
            logging.error("Failed to update Epic Appointment: %s", e)

        # Close the call with a message that matches the patient's outcome
        if confirmation and confirmation.strip().lower() == "cancel":
            self.hangup(
                final_instructions=(
                    "Let the patient know their appointment has been cancelled and that Cedar Health "
                    "will reach out to help them reschedule when they are ready. Thank them and "
                    "wish them a great day."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    "Thank the patient for confirming. Remind them to arrive 10 minutes early "
                    "and bring their insurance card and a valid photo ID. Wish them a great day."
                )
            )

    def recipient_unavailable(self):
        self.hangup(
            final_instructions=(
                "We were unable to reach the patient. Leave a brief voicemail on behalf of Cedar Health "
                f"asking them to call back to confirm or cancel their appointment on {self.appointment_display}."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound appointment confirmation call for Cedar Health via Epic FHIR."
    )
    parser.add_argument("phone", help="Patient phone number to call (E.164 format, e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Full name of the patient")
    parser.add_argument("--appointment-id", required=True, help="Epic Appointment FHIR resource ID")
    args = parser.parse_args()

    logging.info(
        "Initiating appointment confirmation call to %s (%s) for appointment %s",
        args.name,
        args.phone,
        args.appointment_id,
    )

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=AppointmentConfirmationController(
            patient_name=args.name,
            appointment_id=args.appointment_id,
        ),
    )
