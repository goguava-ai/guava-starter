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


agent = guava.Agent(
    name="Jordan",
    organization="Wellspring Wellness",
    purpose="to remind clients of upcoming appointments and confirm their attendance",
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(contact_full_name=call.get_variable("client_name"))


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    if outcome == "unavailable":
        client_name = call.get_variable("client_name")
        logging.info("Unable to reach %s for appointment reminder.", client_name)
        call.hangup(
            final_instructions=(
                f"Leave a friendly voicemail for {client_name} from Wellspring Wellness. "
                "Remind them about their upcoming appointment and ask them to call back "
                "or check their email confirmation if they need to cancel or reschedule. "
                "Keep it brief."
            )
        )
    elif outcome == "available":
        client_name = call.get_variable("client_name")
        appointment_id = call.get_variable("appointment_id")

        appointment = None
        try:
            appointment = get_appointment(appointment_id)
            logging.info(
                "Appointment %s loaded: %s %s",
                appointment_id,
                appointment.get("date", "") if appointment else "",
                appointment.get("time", "") if appointment else "",
            )
        except Exception as e:
            logging.error("Failed to load appointment %s: %s", appointment_id, e)

        call.set_variable("appointment", appointment)
        call.set_variable("appointment_id", appointment_id)

        if not appointment:
            call.hangup(
                final_instructions=(
                    f"Let {client_name} know you're calling from Wellspring Wellness "
                    "about their upcoming appointment, but couldn't retrieve the details. "
                    "Ask them to check their confirmation email. Be friendly and apologetic."
                )
            )
            return

        appt_type = appointment.get("type", "appointment")
        appt_date = appointment.get("date", "")
        appt_time = appointment.get("time", "")
        provider = appointment.get("calendarName", "your provider")

        try:
            dt = datetime.fromisoformat(f"{appt_date}T{appt_time}")
            display_time = dt.strftime("%A, %B %-d at %-I:%M %p")
        except (ValueError, AttributeError):
            display_time = f"{appt_date} at {appt_time}"

        call.set_task(
            "send_reminder",
            objective=(
                f"Remind {client_name} of their upcoming {appt_type} appointment "
                f"with {provider} on {display_time}. Confirm they plan to attend."
            ),
            checklist=[
                guava.Say(
                    f"Hi {client_name}, this is Jordan calling from Wellspring Wellness. "
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
        )


@agent.on_task_complete("send_reminder")
def handle_response(call: guava.Call) -> None:
    attendance = call.get_field("attendance") or ""
    client_name = call.get_variable("client_name")
    appointment = call.get_variable("appointment")
    appointment_id = call.get_variable("appointment_id")
    appt_type = appointment.get("type", "appointment") if appointment else "appointment"

    if "cancel" in attendance:
        cancelled = False
        try:
            cancelled = cancel_appointment(appointment_id)
            logging.info("Appointment %s cancelled: %s", appointment_id, cancelled)
        except Exception as e:
            logging.error("Failed to cancel appointment %s: %s", appointment_id, e)

        call.hangup(
            final_instructions=(
                f"Let {client_name} know their {appt_type} has been cancelled. "
                "Invite them to rebook anytime via our website or by calling us. "
                "Thank them for letting us know and wish them a great day."
            )
        )

    elif "reschedule" in attendance:
        call.hangup(
            final_instructions=(
                f"Let {client_name} know you've noted they'd like to reschedule. "
                "Ask them to visit the website or call back during business hours to pick a new time. "
                "Thank them for calling."
            )
        )

    else:
        logging.info("Client %s confirmed attendance for appointment %s.", client_name, appointment_id)
        appt_date = appointment.get("date", "") if appointment else ""
        appt_time = appointment.get("time", "") if appointment else ""
        location = appointment.get("location", "our office") if appointment else "our office"
        call.hangup(
            final_instructions=(
                f"Thank {client_name} for confirming. "
                f"Remind them to arrive a few minutes early at {location}. "
                "Wish them a great day."
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

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "client_name": args.name,
            "appointment_id": args.appointment_id,
        },
    )
