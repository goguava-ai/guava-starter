import guava
import os
import logging
import argparse
import requests

logging.basicConfig(level=logging.INFO)

PRACTICE_ID = os.environ["ATHENA_PRACTICE_ID"]
BASE_URL = f"https://api.platform.athenahealth.com/v1/{PRACTICE_ID}"


def get_access_token() -> str:
    resp = requests.post(
        "https://api.platform.athenahealth.com/oauth2/v1/token",
        data={"grant_type": "client_credentials"},
        auth=(os.environ["ATHENA_CLIENT_ID"], os.environ["ATHENA_CLIENT_SECRET"]),
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def get_appointment(appointment_id: str, headers: dict) -> dict | None:
    resp = requests.get(
        f"{BASE_URL}/appointments/{appointment_id}",
        headers=headers,
        timeout=10,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    appointments = resp.json().get("appointments", [])
    return appointments[0] if appointments else None


def cancel_appointment(appointment_id: str, headers: dict) -> bool:
    resp = requests.put(
        f"{BASE_URL}/appointments/{appointment_id}",
        headers=headers,
        data={"appointmentstatus": "x"},  # 'x' = cancelled in Athenahealth
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
                "Content-Type": "application/x-www-form-urlencoded",
            }
            self.appointment = get_appointment(appointment_id, self.headers)
        except Exception as e:
            logging.error("Failed to fetch appointment %s pre-call: %s", appointment_id, e)

        self.set_persona(
            organization_name="Maple Medical Group",
            agent_name="Avery",
            agent_purpose=(
                "to confirm upcoming appointments and help patients cancel or reschedule if needed"
            ),
        )

        self.reach_person(
            contact_full_name=self.patient_name,
            on_success=self.confirm_appointment,
            on_failure=self.recipient_unavailable,
        )

    def confirm_appointment(self):
        if not self.appointment:
            self.hangup(
                final_instructions=(
                    f"Let {self.patient_name} know you're calling from Maple Medical Group "
                    "to confirm their upcoming appointment, but you weren't able to retrieve "
                    "the appointment details. Ask them to call the office directly to confirm. "
                    "Be apologetic and helpful."
                )
            )
            return

        appt_date = self.appointment.get("starttime", "")
        appt_type = self.appointment.get("appointmenttype", "your appointment")
        provider = self.appointment.get("providername", "your provider")
        department = self.appointment.get("departmentname", "our office")

        self.set_task(
            objective=(
                f"Confirm {self.patient_name}'s upcoming {appt_type} appointment "
                f"with {provider} at {department} on {appt_date}. "
                "Find out if they plan to attend, and cancel if they cannot make it."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.patient_name}, this is Avery calling from Maple Medical Group. "
                    f"I'm calling to confirm your {appt_type} appointment with {provider} "
                    f"scheduled for {appt_date} at {department}."
                ),
                guava.Field(
                    key="will_attend",
                    field_type="multiple_choice",
                    description="Ask if they plan to attend the appointment.",
                    choices=["yes", "no", "need to reschedule"],
                    required=True,
                ),
            ],
            on_complete=self.handle_response,
        )

    def handle_response(self):
        will_attend = self.get_field("will_attend") or ""
        appt_type = self.appointment.get("appointmenttype", "appointment") if self.appointment else "appointment"

        if "no" in will_attend or "reschedule" in will_attend:
            cancelled = False
            try:
                cancelled = cancel_appointment(self.appointment_id, self.headers)
                logging.info(
                    "Appointment %s cancelled: %s",
                    self.appointment_id, cancelled,
                )
            except Exception as e:
                logging.error("Failed to cancel appointment %s: %s", self.appointment_id, e)

            if "reschedule" in will_attend:
                self.hangup(
                    final_instructions=(
                        f"Let {self.patient_name} know their {appt_type} has been cancelled "
                        "and that a team member will call them back to find a new time. "
                        "Wish them a great day."
                    )
                )
            else:
                self.hangup(
                    final_instructions=(
                        f"Let {self.patient_name} know their {appt_type} has been cancelled. "
                        "Encourage them to call back when they're ready to reschedule. "
                        "Thank them for letting us know and wish them a great day."
                    )
                )
        else:
            logging.info("Appointment %s confirmed by patient.", self.appointment_id)
            self.hangup(
                final_instructions=(
                    f"Thank {self.patient_name} for confirming. Remind them to arrive 10 minutes "
                    "early and bring their insurance card and a photo ID. "
                    "Wish them a great day."
                )
            )

    def recipient_unavailable(self):
        logging.info("Unable to reach %s for appointment confirmation.", self.patient_name)
        self.hangup(
            final_instructions=(
                f"Leave a brief voicemail for {self.patient_name} from Maple Medical Group. "
                "Let them know you're calling to confirm their upcoming appointment and ask them "
                "to call back or reply to their appointment reminder to confirm or cancel. "
                "Keep it concise and friendly."
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Outbound appointment confirmation call via Athenahealth."
    )
    parser.add_argument("phone", help="Patient phone number (E.164, e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Patient's full name")
    parser.add_argument("--appointment-id", required=True, help="Athenahealth appointment ID")
    args = parser.parse_args()

    logging.info(
        "Confirming appointment %s with %s at %s",
        args.appointment_id, args.name, args.phone,
    )

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=AppointmentConfirmationController(
            patient_name=args.name,
            appointment_id=args.appointment_id,
        ),
    )
