import guava
import os
import logging
from guava import logging_utils
import argparse
import requests



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


agent = guava.Agent(
    name="Sam",
    organization="Sunrise Family Practice",
    purpose="to confirm upcoming appointments and help patients cancel if needed",
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    appointment_id = call.get_variable("appointment_id")

    headers = {}
    appointment = None
    try:
        token = get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        appointment = get_appointment(appointment_id, headers)
        logging.info(
            "Appointment %s loaded: status=%s",
            appointment_id,
            appointment.get("status") if appointment else "not found",
        )
    except Exception as e:
        logging.error("Failed to load appointment %s: %s", appointment_id, e)

    call.headers = headers
    call.appointment = appointment

    call.reach_person(contact_full_name=patient_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    patient_name = call.get_variable("patient_name")
    if outcome == "unavailable":
        logging.info("Unable to reach %s.", patient_name)
        call.hangup(
            final_instructions=(
                f"Leave a brief voicemail for {patient_name} from Sunrise Family Practice "
                "asking them to confirm or cancel their upcoming appointment by calling back. "
                "Keep it friendly and concise."
            )
        )
    elif outcome == "available":
        appointment = call.appointment
        if not appointment:
            call.hangup(
                final_instructions=(
                    f"Let {patient_name} know you're calling from Sunrise Family Practice "
                    "to confirm their upcoming appointment, but the details weren't available. "
                    "Ask them to call the office to confirm. Be apologetic."
                )
            )
            return

        # Extract display fields from FHIR Appointment resource
        start = appointment.get("start", "")
        appt_type = ""
        if appointment.get("appointmentType"):
            codings = appointment["appointmentType"].get("coding", [])
            appt_type = codings[0].get("display", "") if codings else ""

        participant_names = []
        for p in appointment.get("participant", []):
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

        call.set_task(
            "appointment_confirmation",
            objective=(
                f"Confirm {patient_name}'s appointment with {provider} on {display_time}."
            ),
            checklist=[
                guava.Say(
                    f"Hi {patient_name}, this is Sam calling from Sunrise Family Practice. "
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
        )


@agent.on_task_complete("appointment_confirmation")
def on_done(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    appointment_id = call.get_variable("appointment_id")
    attendance = call.get_field("attendance") or ""
    appt_type = "appointment"
    if call.appointment and call.appointment.get("appointmentType"):
        codings = call.appointment["appointmentType"].get("coding", [])
        appt_type = codings[0].get("display", "appointment") if codings else "appointment"

    if "cancel" in attendance or "no" in attendance:
        cancelled = False
        try:
            cancelled = cancel_appointment(appointment_id, call.headers)
            logging.info("Appointment %s cancelled: %s", appointment_id, cancelled)
        except Exception as e:
            logging.error("Cancel failed for %s: %s", appointment_id, e)

        call.hangup(
            final_instructions=(
                f"Let {patient_name} know their {appt_type} has been cancelled. "
                "Invite them to call back or go online to reschedule when ready. "
                "Thank them and wish them a great day."
            )
        )
    elif "reschedule" in attendance:
        call.hangup(
            final_instructions=(
                f"Acknowledge that {patient_name} needs to reschedule. "
                "Let them know a scheduling coordinator will follow up within one business day. "
                "Thank them for letting us know."
            )
        )
    else:
        logging.info("Appointment %s confirmed.", appointment_id)
        call.hangup(
            final_instructions=(
                f"Thank {patient_name} for confirming. Remind them to arrive 10 minutes early "
                "and bring their insurance card and photo ID. Wish them a great day."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound appointment confirmation via eClinicalWorks FHIR."
    )
    parser.add_argument("phone", help="Patient phone number (E.164)")
    parser.add_argument("--name", required=True, help="Patient's full name")
    parser.add_argument("--appointment-id", required=True, help="FHIR Appointment ID")
    args = parser.parse_args()

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "patient_name": args.name,
            "appointment_id": args.appointment_id,
        },
    )
