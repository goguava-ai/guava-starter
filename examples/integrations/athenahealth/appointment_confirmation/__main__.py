import guava
import os
import logging
from guava import logging_utils
import argparse
import requests


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


agent = guava.Agent(
    name="Avery",
    organization="Maple Medical Group",
    purpose=(
        "to confirm upcoming appointments and help patients cancel or reschedule if needed"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(contact_full_name=call.get_variable("patient_name"))


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    if outcome == "unavailable":
        logging.info("Unable to reach %s for appointment confirmation.", call.get_variable("patient_name"))
        call.hangup(
            final_instructions=(
                f"Leave a brief voicemail for {call.get_variable('patient_name')} from Maple Medical Group. "
                "Let them know you're calling to confirm their upcoming appointment and ask them "
                "to call back or reply to their appointment reminder to confirm or cancel. "
                "Keep it concise and friendly."
            )
        )
    elif outcome == "available":
        patient_name = call.get_variable("patient_name")
        appointment_id = call.get_variable("appointment_id")

        headers = {}
        appointment = None
        try:
            token = get_access_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/x-www-form-urlencoded",
            }
            appointment = get_appointment(appointment_id, headers)
        except Exception as e:
            logging.error("Failed to fetch appointment %s pre-call: %s", appointment_id, e)

        call.data = {"headers": headers, "appointment": appointment}

        if not appointment:
            call.hangup(
                final_instructions=(
                    f"Let {patient_name} know you're calling from Maple Medical Group "
                    "to confirm their upcoming appointment, but you weren't able to retrieve "
                    "the appointment details. Ask them to call the office directly to confirm. "
                    "Be apologetic and helpful."
                )
            )
            return

        appt_date = appointment.get("starttime", "")
        appt_type = appointment.get("appointmenttype", "your appointment")
        provider = appointment.get("providername", "your provider")
        department = appointment.get("departmentname", "our office")

        call.set_task(
            "handle_confirmation_response",
            objective=(
                f"Confirm {patient_name}'s upcoming {appt_type} appointment "
                f"with {provider} at {department} on {appt_date}. "
                "Find out if they plan to attend, and cancel if they cannot make it."
            ),
            checklist=[
                guava.Say(
                    f"Hi {patient_name}, this is Avery calling from Maple Medical Group. "
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
        )


@agent.on_task_complete("handle_confirmation_response")
def on_done(call: guava.Call) -> None:
    will_attend = call.get_field("will_attend") or ""
    patient_name = call.get_variable("patient_name")
    appointment_id = call.get_variable("appointment_id")
    appointment = call.data.get("appointment") if call.data else None
    headers = call.data.get("headers", {}) if call.data else {}
    appt_type = appointment.get("appointmenttype", "appointment") if appointment else "appointment"

    if "no" in will_attend or "reschedule" in will_attend:
        cancelled = False
        try:
            cancelled = cancel_appointment(appointment_id, headers)
            logging.info(
                "Appointment %s cancelled: %s",
                appointment_id, cancelled,
            )
        except Exception as e:
            logging.error("Failed to cancel appointment %s: %s", appointment_id, e)

        if "reschedule" in will_attend:
            call.hangup(
                final_instructions=(
                    f"Let {patient_name} know their {appt_type} has been cancelled "
                    "and that a team member will call them back to find a new time. "
                    "Wish them a great day."
                )
            )
        else:
            call.hangup(
                final_instructions=(
                    f"Let {patient_name} know their {appt_type} has been cancelled. "
                    "Encourage them to call back when they're ready to reschedule. "
                    "Thank them for letting us know and wish them a great day."
                )
            )
    else:
        logging.info("Appointment %s confirmed by patient.", appointment_id)
        call.hangup(
            final_instructions=(
                f"Thank {patient_name} for confirming. Remind them to arrive 10 minutes "
                "early and bring their insurance card and a photo ID. "
                "Wish them a great day."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
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

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "patient_name": args.name,
            "appointment_id": args.appointment_id,
        },
    )
