import guava
import os
import logging
from guava import logging_utils
import argparse
import requests


BASE_URL = "https://api.mindbodyonline.com/public/v6"
API_KEY = os.environ["MINDBODY_API_KEY"]
SITE_ID = os.environ["MINDBODY_SITE_ID"]
STAFF_TOKEN = os.environ["MINDBODY_STAFF_TOKEN"]

HEADERS = {
    "API-Key": API_KEY,
    "SiteId": SITE_ID,
    "Authorization": f"Bearer {STAFF_TOKEN}",
    "Content-Type": "application/json",
}


def fetch_client_appointments(client_id: str):
    """Return upcoming staff appointments for this client."""
    resp = requests.get(
        f"{BASE_URL}/appointment/staffAppointments",
        headers=HEADERS,
        params={"clientId": client_id},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("Appointments", [])


def cancel_appointment(appointment_id: int):
    """Cancel a Mindbody appointment by ID."""
    resp = requests.post(
        f"{BASE_URL}/appointment/cancelAppointment",
        headers=HEADERS,
        json={"AppointmentId": appointment_id},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def send_confirmation_email(client_id: str, appointment_id: int):
    """Trigger a Mindbody auto-email to confirm the appointment."""
    resp = requests.post(
        f"{BASE_URL}/client/sendautoemail",
        headers=HEADERS,
        json={
            "ClientId": client_id,
            "AutoEmailTypeId": 1,  # Appointment reminder type
            "AppointmentId": appointment_id,
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


class AppointmentReminderController(guava.CallController):
    def __init__(self, client_name: str, client_id: str, appointment_id: int,
                 appointment_datetime: str, service_name: str, staff_name: str):
        super().__init__()
        self.client_name = client_name
        self.client_id = client_id
        self.appointment_id = appointment_id
        self.appointment_datetime = appointment_datetime
        self.service_name = service_name
        self.staff_name = staff_name

        # Pre-fetch the appointment to verify it still exists.
        try:
            appointments = fetch_client_appointments(client_id)
            self.appointment = next(
                (a for a in appointments if a.get("Id") == appointment_id), None
            )
        except Exception as e:
            logging.error("Failed to pre-fetch appointment: %s", e)
            self.appointment = None

        self.set_persona(
            organization_name="Peak Performance Studio",
            agent_name="Jordan",
            agent_purpose="to confirm upcoming appointments with clients",
        )

        self.reach_person(
            contact_full_name=self.client_name,
            on_success=self.begin_call,
            on_failure=self.recipient_unavailable,
        )

    def begin_call(self):
        self.set_task(
            objective=(
                f"Confirm or cancel {self.client_name}'s appointment tomorrow "
                f"({self.appointment_datetime}) for {self.service_name} with {self.staff_name}."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.client_name}, this is Jordan calling from Peak Performance Studio. "
                    f"I'm reaching out to confirm your {self.service_name} session with "
                    f"{self.staff_name} scheduled for tomorrow at {self.appointment_datetime}. "
                    "This will just take a moment!"
                ),
                guava.Field(
                    key="confirmation",
                    field_type="multiple_choice",
                    description=(
                        f"Ask {self.client_name} whether they will be attending the appointment "
                        "or if they need to cancel."
                    ),
                    choices=["confirm", "cancel"],
                    required=True,
                ),
                guava.Field(
                    key="cancel_reason",
                    field_type="text",
                    description=(
                        "If they chose to cancel, ask briefly if there is a reason — "
                        "illness, schedule conflict, or other. This is optional; accept 'no reason given'."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="reschedule_interest",
                    field_type="multiple_choice",
                    description=(
                        "If they are canceling, ask if they would like help rescheduling for a future date."
                    ),
                    choices=["yes, reschedule", "no thanks"],
                    required=False,
                ),
            ],
            on_complete=self.handle_outcome,
        )

    def handle_outcome(self):
        confirmation = self.get_field("confirmation")
        reschedule = self.get_field("reschedule_interest")

        if confirmation == "cancel":
            try:
                cancel_appointment(self.appointment_id)
                logging.info(
                    "Cancelled appointment %s for client %s", self.appointment_id, self.client_id
                )
            except Exception as e:
                logging.error("Failed to cancel appointment %s: %s", self.appointment_id, e)

            if reschedule == "yes, reschedule":
                self.hangup(
                    final_instructions=(
                        f"Thank {self.client_name} for letting us know. Confirm the appointment has been "
                        "cancelled and let them know a team member will follow up to help reschedule. "
                        "Be understanding and warm."
                    )
                )
            else:
                self.hangup(
                    final_instructions=(
                        f"Thank {self.client_name} for letting us know. Confirm the appointment has been "
                        "cancelled and invite them to call back whenever they are ready to book their next session. "
                        "Be warm and wish them well."
                    )
                )
        else:
            # Confirmed — send a confirmation email.
            try:
                send_confirmation_email(self.client_id, self.appointment_id)
                logging.info(
                    "Sent confirmation email to client %s for appointment %s",
                    self.client_id, self.appointment_id,
                )
            except Exception as e:
                logging.error("Failed to send confirmation email: %s", e)

            self.hangup(
                final_instructions=(
                    f"Confirm to {self.client_name} that their appointment is all set for tomorrow "
                    f"at {self.appointment_datetime}. Remind them to arrive 10 minutes early and "
                    "bring water. Let them know a confirmation email is on its way. "
                    "Be enthusiastic and wish them a great session."
                )
            )

    def recipient_unavailable(self):
        self.hangup(
            final_instructions=(
                f"Leave a friendly voicemail for {self.client_name} reminding them about their "
                f"{self.service_name} appointment with {self.staff_name} tomorrow at "
                f"{self.appointment_datetime}. Ask them to call Peak Performance Studio "
                "if they need to make any changes. Keep it brief and warm."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Call a client the day before their appointment to confirm or cancel."
    )
    parser.add_argument("phone", help="Client phone number in E.164 format, e.g. +12125550100")
    parser.add_argument("--client-id", required=True, help="Mindbody client ID")
    parser.add_argument("--name", required=True, help="Client full name")
    parser.add_argument("--appointment-id", required=True, type=int, help="Mindbody appointment ID")
    parser.add_argument(
        "--appointment-datetime",
        required=True,
        help="Human-readable appointment time, e.g. '9:00 AM'",
    )
    parser.add_argument(
        "--service-name",
        required=True,
        help="Service name, e.g. 'Personal Training (60 min)'",
    )
    parser.add_argument("--staff-name", required=True, help="Trainer or instructor name")
    args = parser.parse_args()

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=AppointmentReminderController(
            client_name=args.name,
            client_id=args.client_id,
            appointment_id=args.appointment_id,
            appointment_datetime=args.appointment_datetime,
            service_name=args.service_name,
            staff_name=args.staff_name,
        ),
    )
