import guava
import os
import logging
import argparse
import requests

logging.basicConfig(level=logging.INFO)


def get_access_token() -> str:
    resp = requests.post(
        os.environ["ECW_TOKEN_URL"],
        data={"grant_type": "client_credentials", "scope": "system/*.read system/*.write"},
        auth=(os.environ["ECW_CLIENT_ID"], os.environ["ECW_CLIENT_SECRET"]),
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def get_appointment(appointment_id: str, headers: dict) -> dict | None:
    base_url = os.environ["ECW_BASE_URL"]
    resp = requests.get(
        f"{base_url}/Appointment/{appointment_id}",
        headers=headers,
        timeout=10,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def cancel_appointment(appointment_id: str, headers: dict) -> bool:
    """Patches appointment status to 'cancelled' in eClinicalWorks FHIR."""
    base_url = os.environ["ECW_BASE_URL"]
    patch_headers = {**headers, "Content-Type": "application/json-patch+json"}
    resp = requests.patch(
        f"{base_url}/Appointment/{appointment_id}",
        headers=patch_headers,
        json=[{"op": "replace", "path": "/status", "value": "cancelled"}],
        timeout=10,
    )
    return resp.ok


class AppointmentConfirmationController(guava.CallController):
    def __init__(self, patient_name: str, appointment_id: str):
        super().__init__()
        self.patient_name = patient_name
        self.appointment_id = appointment_id
        self.appointment = None
        self.headers = {}

        try:
            token = get_access_token()
            self.headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
            self.appointment = get_appointment(appointment_id, self.headers)
            logging.info(
                "Appointment %s loaded: status=%s",
                appointment_id,
                self.appointment.get("status") if self.appointment else "not found",
            )
        except Exception as e:
            logging.error("Failed to load appointment %s: %s", appointment_id, e)

        self.set_persona(
            organization_name="Sunrise Family Practice",
            agent_name="Sam",
            agent_purpose=(
                "to confirm upcoming appointments and help patients cancel if needed"
            ),
        )

        self.reach_person(
            contact_full_name=self.patient_name,
            on_success=self.confirm,
            on_failure=self.leave_voicemail,
        )

    def confirm(self):
        if not self.appointment:
            self.hangup(
                final_instructions=(
                    f"Let {self.patient_name} know you're calling from Sunrise Family Practice "
                    "to confirm their upcoming appointment, but the details weren't available. "
                    "Ask them to call the office to confirm. Be apologetic."
                )
            )
            return

        # Extract display fields from FHIR Appointment resource
        status = self.appointment.get("status", "")
        start = self.appointment.get("start", "")
        appt_type = ""
        if self.appointment.get("appointmentType"):
            codings = self.appointment["appointmentType"].get("coding", [])
            appt_type = codings[0].get("display", "") if codings else ""

        participant_names = []
        for p in self.appointment.get("participant", []):
            actor = p.get("actor", {})
            display = actor.get("display", "")
            if display and "Patient" not in actor.get("reference", "Patient"):
                participant_names.append(display)
        provider = participant_names[0] if participant_names else "your provider"

        try:
            from datetime import datetime
            dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            display_time = dt.strftime("%A, %B %-d at %-I:%M %p")
        except (ValueError, AttributeError):
            display_time = start or "your upcoming appointment"

        self.set_task(
            objective=(
                f"Confirm {self.patient_name}'s appointment with {provider} on {display_time}."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.patient_name}, this is Sam calling from Sunrise Family Practice. "
                    f"I'm calling to confirm your appointment with {provider} on {display_time}."
                ),
                guava.Field(
                    key="attendance",
                    field_type="multiple_choice",
                    description="Ask if they plan to attend, need to cancel, or want to reschedule.",
                    choices=["yes", "no / cancel", "need to reschedule"],
                    required=True,
                ),
            ],
            on_complete=self.handle_response,
        )

    def handle_response(self):
        attendance = self.get_field("attendance") or ""
        appt_type = "appointment"
        if self.appointment and self.appointment.get("appointmentType"):
            codings = self.appointment["appointmentType"].get("coding", [])
            appt_type = codings[0].get("display", "appointment") if codings else "appointment"

        if "cancel" in attendance or "no" in attendance:
            cancelled = False
            try:
                cancelled = cancel_appointment(self.appointment_id, self.headers)
                logging.info("Appointment %s cancelled: %s", self.appointment_id, cancelled)
            except Exception as e:
                logging.error("Cancel failed for %s: %s", self.appointment_id, e)

            self.hangup(
                final_instructions=(
                    f"Let {self.patient_name} know their {appt_type} has been cancelled. "
                    "Invite them to call back or go online to reschedule when ready. "
                    "Thank them and wish them a great day."
                )
            )
        elif "reschedule" in attendance:
            self.hangup(
                final_instructions=(
                    f"Acknowledge that {self.patient_name} needs to reschedule. "
                    "Let them know a scheduling coordinator will follow up within one business day. "
                    "Thank them for letting us know."
                )
            )
        else:
            logging.info("Appointment %s confirmed.", self.appointment_id)
            self.hangup(
                final_instructions=(
                    f"Thank {self.patient_name} for confirming. Remind them to arrive 10 minutes early "
                    "and bring their insurance card and photo ID. Wish them a great day."
                )
            )

    def leave_voicemail(self):
        logging.info("Unable to reach %s.", self.patient_name)
        self.hangup(
            final_instructions=(
                f"Leave a brief voicemail for {self.patient_name} from Sunrise Family Practice "
                "asking them to confirm or cancel their upcoming appointment by calling back. "
                "Keep it friendly and concise."
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Outbound appointment confirmation via eClinicalWorks FHIR."
    )
    parser.add_argument("phone", help="Patient phone number (E.164)")
    parser.add_argument("--name", required=True, help="Patient's full name")
    parser.add_argument("--appointment-id", required=True, help="FHIR Appointment ID")
    args = parser.parse_args()

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=AppointmentConfirmationController(
            patient_name=args.name,
            appointment_id=args.appointment_id,
        ),
    )
