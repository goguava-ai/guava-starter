import guava
import os
import logging
from guava import logging_utils
import argparse
import requests
from datetime import datetime


BASE_URL = "https://acuityscheduling.com/api/v1"
AUTH = (os.environ["ACUITY_USER_ID"], os.environ["ACUITY_API_KEY"])


def get_appointment(appointment_id: str) -> dict | None:
    resp = requests.get(f"{BASE_URL}/appointments/{appointment_id}", auth=AUTH, timeout=10)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def cancel_appointment(appointment_id: str) -> bool:
    resp = requests.put(
        f"{BASE_URL}/appointments/{appointment_id}/cancel",
        auth=AUTH,
        timeout=10,
    )
    return resp.ok


class AppointmentReminderController(guava.CallController):
    def __init__(self, client_name: str, appointment_id: str):
        super().__init__()
        self.client_name = client_name
        self.appointment_id = appointment_id
        self.appointment = None

        try:
            self.appointment = get_appointment(appointment_id)
            logging.info(
                "Appointment %s loaded: %s %s",
                appointment_id,
                self.appointment.get("date", "") if self.appointment else "",
                self.appointment.get("time", "") if self.appointment else "",
            )
        except Exception as e:
            logging.error("Failed to load appointment %s: %s", appointment_id, e)

        self.set_persona(
            organization_name="Wellspring Wellness",
            agent_name="Jordan",
            agent_purpose=(
                "to remind clients of upcoming appointments and confirm their attendance"
            ),
        )

        self.reach_person(
            contact_full_name=self.client_name,
            on_success=self.send_reminder,
            on_failure=self.leave_voicemail,
        )

    def send_reminder(self):
        if not self.appointment:
            self.hangup(
                final_instructions=(
                    f"Let {self.client_name} know you're calling from Wellspring Wellness "
                    "about their upcoming appointment, but couldn't retrieve the details. "
                    "Ask them to check their confirmation email. Be friendly and apologetic."
                )
            )
            return

        appt_type = self.appointment.get("type", "appointment")
        appt_date = self.appointment.get("date", "")
        appt_time = self.appointment.get("time", "")
        provider = self.appointment.get("calendarName", "your provider")

        try:
            dt = datetime.fromisoformat(f"{appt_date}T{appt_time}")
            display_time = dt.strftime("%A, %B %-d at %-I:%M %p")
        except (ValueError, AttributeError):
            display_time = f"{appt_date} at {appt_time}"

        self.set_task(
            objective=(
                f"Remind {self.client_name} of their upcoming {appt_type} appointment "
                f"with {provider} on {display_time}. Confirm they plan to attend."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.client_name}, this is Jordan calling from Wellspring Wellness. "
                    f"I'm reaching out to remind you about your {appt_type} appointment "
                    f"with {provider} on {display_time}."
                ),
                guava.Field(
                    key="attendance",
                    field_type="multiple_choice",
                    description="Ask if they plan to attend or if they need to cancel.",
                    choices=["yes, I'll be there", "no, please cancel", "need to reschedule"],
                    required=True,
                ),
            ],
            on_complete=self.handle_response,
        )

    def handle_response(self):
        attendance = self.get_field("attendance") or ""
        appt_type = self.appointment.get("type", "appointment") if self.appointment else "appointment"

        if "cancel" in attendance:
            cancelled = False
            try:
                cancelled = cancel_appointment(self.appointment_id)
                logging.info("Appointment %s cancelled: %s", self.appointment_id, cancelled)
            except Exception as e:
                logging.error("Failed to cancel appointment %s: %s", self.appointment_id, e)

            self.hangup(
                final_instructions=(
                    f"Let {self.client_name} know their {appt_type} has been cancelled. "
                    "Invite them to rebook anytime via our website or by calling us. "
                    "Thank them for letting us know and wish them a great day."
                )
            )

        elif "reschedule" in attendance:
            self.hangup(
                final_instructions=(
                    f"Let {self.client_name} know you've noted they'd like to reschedule. "
                    "Ask them to visit the website or call back during business hours to pick a new time. "
                    "Thank them for calling."
                )
            )

        else:
            logging.info("Client %s confirmed attendance for appointment %s.", self.client_name, self.appointment_id)
            appt_date = self.appointment.get("date", "") if self.appointment else ""
            appt_time = self.appointment.get("time", "") if self.appointment else ""
            location = self.appointment.get("location", "our office") if self.appointment else "our office"
            self.hangup(
                final_instructions=(
                    f"Thank {self.client_name} for confirming. "
                    f"Remind them to arrive a few minutes early at {location}. "
                    "Wish them a great day."
                )
            )

    def leave_voicemail(self):
        logging.info("Unable to reach %s for appointment reminder.", self.client_name)
        self.hangup(
            final_instructions=(
                f"Leave a friendly voicemail for {self.client_name} from Wellspring Wellness. "
                "Remind them about their upcoming appointment and ask them to call back "
                "or check their email confirmation if they need to cancel or reschedule. "
                "Keep it brief."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound appointment reminder call via Acuity Scheduling."
    )
    parser.add_argument("phone", help="Client phone number (E.164, e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Client's full name")
    parser.add_argument("--appointment-id", required=True, help="Acuity appointment ID")
    args = parser.parse_args()

    logging.info(
        "Sending appointment reminder to %s (%s) for appointment %s",
        args.name, args.phone, args.appointment_id,
    )

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=AppointmentReminderController(
            client_name=args.name,
            appointment_id=args.appointment_id,
        ),
    )
