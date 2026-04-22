import argparse
import logging
import os
from datetime import datetime

import guava
import requests
from guava import logging_utils

BASE_URL = "https://acuityscheduling.com/api/v1"
AUTH = (os.environ["ACUITY_USER_ID"], os.environ["ACUITY_API_KEY"])


def get_appointment(appointment_id: str) -> dict | None:
    resp = requests.get(f"{BASE_URL}/appointments/{appointment_id}", auth=AUTH, timeout=10)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def get_available_times(appointment_type_id: int, date: str) -> list:
    resp = requests.get(
        f"{BASE_URL}/availability/times",
        auth=AUTH,
        params={"appointmentTypeID": appointment_type_id, "date": date},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def reschedule_appointment(appointment_id: str, new_datetime: str) -> dict | None:
    resp = requests.put(
        f"{BASE_URL}/appointments/{appointment_id}/reschedule",
        auth=AUTH,
        json={"datetime": new_datetime},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


agent = guava.Agent(
    name="Jordan",
    organization="Wellspring Wellness",
    purpose="to help clients reschedule their Wellspring Wellness appointments",
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    client_name = call.get_variable("client_name")
    appointment_id = call.get_variable("appointment_id")

    appointment = None
    try:
        appointment = get_appointment(appointment_id)
        logging.info("Loaded appointment %s for rescheduling.", appointment_id)
    except Exception as e:
        logging.error("Failed to load appointment %s: %s", appointment_id, e)

    call.set_variable("appointment", appointment)
    call.set_variable("appointment_id", appointment_id)
    call.set_variable("new_slot_time", None)

    appt_display = ""
    if appointment:
        appt_date = appointment.get("date", "")
        appt_time = appointment.get("time", "")
        appt_type = appointment.get("type", "appointment")
        try:
            dt = datetime.fromisoformat(f"{appt_date}T{appt_time}")
            appt_display = f"their {appt_type} on {dt.strftime('%A, %B %-d at %-I:%M %p')}"
        except (ValueError, AttributeError):
            appt_display = f"their {appt_type} on {appt_date}"

    call.set_task(
        "collect_new_date",
        objective=(
            f"Help {client_name} reschedule {appt_display or 'their appointment'}. "
            "Collect their preferred new date and find an available time."
        ),
        checklist=[
            guava.Say(
                f"Hi {client_name}, this is Jordan from Wellspring Wellness. "
                f"I understand you'd like to reschedule {appt_display or 'your appointment'}. "
                "I'm happy to help with that."
            ),
            guava.Field(
                key="new_preferred_date",
                field_type="text",
                description=(
                    "Ask what new date works best for them. "
                    "Capture in YYYY-MM-DD format."
                ),
                required=True,
            ),
        ],
    )


@agent.on_task_complete("collect_new_date")
def find_new_slot(call: guava.Call) -> None:
    client_name = call.get_variable("client_name")
    new_date = call.get_field("new_preferred_date") or ""
    appointment = call.get_variable("appointment")
    appointment_type_id = appointment.get("appointmentTypeID", 0) if appointment else 0

    logging.info("Searching availability for %s on %s", client_name, new_date)

    try:
        times = get_available_times(appointment_type_id, new_date)
        if times:
            new_slot_time = times[0].get("time", "")
            try:
                dt = datetime.fromisoformat(new_slot_time)
                display_time = dt.strftime("%A, %B %-d at %-I:%M %p")
            except (ValueError, AttributeError):
                display_time = new_slot_time

            call.set_variable("new_slot_time", new_slot_time)
            call.set_variable("display_time", display_time)

            call.set_task(
                "confirm_new_slot",
                objective=(
                    f"A new slot has been found for {client_name}. "
                    "Present it and ask for confirmation."
                ),
                checklist=[
                    guava.Say(
                        f"I have an opening on {display_time}. "
                        "Would that work for you?"
                    ),
                    guava.Field(
                        key="confirmed",
                        field_type="multiple_choice",
                        description="Ask if the new time works for them.",
                        choices=["yes", "no"],
                        required=True,
                    ),
                ],
            )
            return

    except Exception as e:
        logging.error("Availability search failed: %s", e)

    call.hangup(
        final_instructions=(
            f"Apologize to {client_name} — there's no availability on their preferred date. "
            "Ask them to visit the website or call back during business hours to find a time. "
            "Thank them for their patience."
        )
    )


@agent.on_task_complete("confirm_new_slot")
def complete_reschedule(call: guava.Call) -> None:
    client_name = call.get_variable("client_name")
    confirmed = call.get_field("confirmed") or ""
    display_time = call.get_variable("display_time")
    new_slot_time = call.get_variable("new_slot_time")
    appointment_id = call.get_variable("appointment_id")

    if confirmed.lower() != "yes":
        call.hangup(
            final_instructions=(
                f"Acknowledge that {client_name} would like a different time. "
                "Invite them to visit the website or call back. Thank them."
            )
        )
        return

    rescheduled = None
    try:
        rescheduled = reschedule_appointment(appointment_id, new_slot_time)
        logging.info("Appointment %s rescheduled: %s", appointment_id, rescheduled.get("id") if rescheduled else None)
    except Exception as e:
        logging.error("Reschedule failed for %s: %s", appointment_id, e)

    if rescheduled:
        call.hangup(
            final_instructions=(
                f"Confirm to {client_name} that their appointment has been rescheduled "
                f"to {display_time}. Let them know a new confirmation email is on its way. "
                "Thank them and wish them a great day."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Apologize to {client_name} — the reschedule couldn't be completed online. "
                "Ask them to call back during business hours and we'll sort it out. "
                "Thank them for their patience."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Inbound appointment reschedule via Acuity Scheduling."
    )
    parser.add_argument("phone", help="Client phone number (E.164)")
    parser.add_argument("--name", required=True, help="Client's full name")
    parser.add_argument("--appointment-id", required=True, help="Acuity appointment ID to reschedule")
    args = parser.parse_args()

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "client_name": args.name,
            "appointment_id": args.appointment_id,
        },
    )
