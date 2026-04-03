import guava
import os
import logging
import argparse
import requests
from datetime import datetime

logging.basicConfig(level=logging.INFO)


def get_access_token() -> str:
    resp = requests.post(
        os.environ["NEXTGEN_TOKEN_URL"],
        data={"grant_type": "client_credentials", "scope": "system/*.read system/*.write"},
        auth=(os.environ["NEXTGEN_CLIENT_ID"], os.environ["NEXTGEN_CLIENT_SECRET"]),
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def get_appointment(appointment_id: str, headers: dict) -> dict | None:
    base_url = os.environ["NEXTGEN_BASE_URL"]
    resp = requests.get(f"{base_url}/Appointment/{appointment_id}", headers=headers, timeout=10)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def cancel_appointment(appointment_id: str, headers: dict) -> bool:
    base_url = os.environ["NEXTGEN_BASE_URL"]
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
            self.headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            self.appointment = get_appointment(appointment_id, self.headers)
            logging.info("Appointment %s loaded from NextGen.", appointment_id)
        except Exception as e:
            logging.error("Failed to load appointment %s: %s", appointment_id, e)

        self.set_persona(
            organization_name="Metro Specialty Clinic",
            agent_name="Morgan",
            agent_purpose="to confirm upcoming appointments and help patients cancel if needed",
        )

        self.reach_person(
            contact_full_name=self.patient_name,
            on_success=self.confirm_appointment,
            on_failure=self.leave_voicemail,
        )

    def confirm_appointment(self):
        if not self.appointment:
            self.hangup(
                final_instructions=(
                    f"Let {self.patient_name} know you're calling from Metro Specialty Clinic "
                    "to confirm their appointment, but you couldn't retrieve the details. "
                    "Ask them to call the office. Be apologetic."
                )
            )
            return

        start = self.appointment.get("start", "")
        appt_type_coding = self.appointment.get("appointmentType", {}).get("coding", [])
        appt_type = appt_type_coding[0].get("display", "appointment") if appt_type_coding else "appointment"

        provider = ""
        for p in self.appointment.get("participant", []):
            ref = p.get("actor", {}).get("reference", "")
            display = p.get("actor", {}).get("display", "")
            if "Practitioner" in ref and display:
                provider = display
                break
        provider = provider or "your provider"

        try:
            dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            display_time = dt.strftime("%A, %B %-d at %-I:%M %p")
        except (ValueError, AttributeError):
            display_time = start or "your upcoming appointment"

        self.set_task(
            objective=f"Confirm {self.patient_name}'s {appt_type} with {provider} on {display_time}.",
            checklist=[
                guava.Say(
                    f"Hi {self.patient_name}, this is Morgan calling from Metro Specialty Clinic. "
                    f"I'm calling to confirm your {appt_type} appointment with {provider} "
                    f"scheduled for {display_time}."
                ),
                guava.Field(
                    key="attendance",
                    field_type="multiple_choice",
                    description="Ask if they plan to attend, need to cancel, or need to reschedule.",
                    choices=["yes, I'll be there", "need to cancel", "need to reschedule"],
                    required=True,
                ),
            ],
            on_complete=lambda: self.handle_response(appt_type, display_time),
        )

    def handle_response(self, appt_type: str, display_time: str):
        attendance = self.get_field("attendance") or ""

        if "cancel" in attendance:
            try:
                cancelled = cancel_appointment(self.appointment_id, self.headers)
                logging.info("Appointment %s cancelled: %s", self.appointment_id, cancelled)
            except Exception as e:
                logging.error("Cancel failed: %s", e)
            self.hangup(
                final_instructions=(
                    f"Let {self.patient_name} know their {appt_type} has been cancelled. "
                    "Invite them to call back or go online to reschedule. Wish them a great day."
                )
            )
        elif "reschedule" in attendance:
            self.hangup(
                final_instructions=(
                    f"Let {self.patient_name} know a scheduling coordinator will call them back "
                    "with new available times. Thank them for letting us know."
                )
            )
        else:
            logging.info("Appointment %s confirmed by %s.", self.appointment_id, self.patient_name)
            self.hangup(
                final_instructions=(
                    f"Thank {self.patient_name} for confirming. Remind them to arrive a few minutes "
                    "early and bring their insurance card and photo ID. Wish them a great day."
                )
            )

    def leave_voicemail(self):
        self.hangup(
            final_instructions=(
                f"Leave a brief voicemail for {self.patient_name} from Metro Specialty Clinic "
                "asking them to confirm or cancel their upcoming appointment by calling back. "
                "Be brief and friendly."
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Outbound appointment confirmation via NextGen FHIR.")
    parser.add_argument("phone", help="Patient phone number (E.164)")
    parser.add_argument("--name", required=True)
    parser.add_argument("--appointment-id", required=True)
    args = parser.parse_args()

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=AppointmentConfirmationController(
            patient_name=args.name,
            appointment_id=args.appointment_id,
        ),
    )
