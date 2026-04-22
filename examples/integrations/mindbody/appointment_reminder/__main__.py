import argparse
import logging
import os

import guava
import requests
from guava import logging_utils

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


agent = guava.Agent(
    name="Jordan",
    organization="Peak Performance Studio",
    purpose="to confirm upcoming appointments with clients",
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    client_name = call.get_variable("client_name")
    client_id = call.get_variable("client_id")
    appointment_id = int(call.get_variable("appointment_id"))

    # Pre-fetch the appointment to verify it still exists.
    appointment = None
    try:
        appointments = fetch_client_appointments(client_id)
        appointment = next(
            (a for a in appointments if a.get("Id") == appointment_id), None
        )
    except Exception as e:
        logging.error("Failed to pre-fetch appointment: %s", e)

    call.reach_person(contact_full_name=client_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    client_name = call.get_variable("client_name")
    appointment_datetime = call.get_variable("appointment_datetime")
    service_name = call.get_variable("service_name")
    staff_name = call.get_variable("staff_name")

    if outcome == "unavailable":
        call.hangup(
            final_instructions=(
                f"Leave a friendly voicemail for {client_name} reminding them about their "
                f"{service_name} appointment with {staff_name} tomorrow at "
                f"{appointment_datetime}. Ask them to call Peak Performance Studio "
                "if they need to make any changes. Keep it brief and warm."
            )
        )
    elif outcome == "available":
        call.set_task(
            "collect_confirmation",
            objective=(
                f"Confirm or cancel {client_name}'s appointment tomorrow "
                f"({appointment_datetime}) for {service_name} with {staff_name}."
            ),
            checklist=[
                guava.Say(
                    f"Hi {client_name}, this is Jordan calling from Peak Performance Studio. "
                    f"I'm reaching out to confirm your {service_name} session with "
                    f"{staff_name} scheduled for tomorrow at {appointment_datetime}. "
                    "This will just take a moment!"
                ),
                guava.Field(
                    key="confirmation",
                    field_type="multiple_choice",
                    description=(
                        f"Ask {client_name} whether they will be attending the appointment "
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
        )


@agent.on_task_complete("collect_confirmation")
def handle_outcome(call: guava.Call) -> None:
    client_name = call.get_variable("client_name")
    client_id = call.get_variable("client_id")
    appointment_id = int(call.get_variable("appointment_id"))
    appointment_datetime = call.get_variable("appointment_datetime")
    confirmation = call.get_field("confirmation")
    reschedule = call.get_field("reschedule_interest")

    if confirmation == "cancel":
        try:
            cancel_appointment(appointment_id)
            logging.info(
                "Cancelled appointment %s for client %s", appointment_id, client_id
            )
        except Exception as e:
            logging.error("Failed to cancel appointment %s: %s", appointment_id, e)

        if reschedule == "yes, reschedule":
            call.hangup(
                final_instructions=(
                    f"Thank {client_name} for letting us know. Confirm the appointment has been "
                    "cancelled and let them know a team member will follow up to help reschedule. "
                    "Be understanding and warm."
                )
            )
        else:
            call.hangup(
                final_instructions=(
                    f"Thank {client_name} for letting us know. Confirm the appointment has been "
                    "cancelled and invite them to call back whenever they are ready to book their next session. "
                    "Be warm and wish them well."
                )
            )
    else:
        # Confirmed — send a confirmation email.
        try:
            send_confirmation_email(client_id, appointment_id)
            logging.info(
                "Sent confirmation email to client %s for appointment %s",
                client_id, appointment_id,
            )
        except Exception as e:
            logging.error("Failed to send confirmation email: %s", e)

        call.hangup(
            final_instructions=(
                f"Confirm to {client_name} that their appointment is all set for tomorrow "
                f"at {appointment_datetime}. Remind them to arrive 10 minutes early and "
                "bring water. Let them know a confirmation email is on its way. "
                "Be enthusiastic and wish them a great session."
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

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "client_name": args.name,
            "client_id": args.client_id,
            "appointment_id": str(args.appointment_id),
            "appointment_datetime": args.appointment_datetime,
            "service_name": args.service_name,
            "staff_name": args.staff_name,
        },
    )
