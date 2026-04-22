import guava
import os
import logging
from guava import logging_utils
import argparse
import requests
from datetime import datetime



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


agent = guava.Agent(
    name="Morgan",
    organization="Metro Specialty Clinic",
    purpose="to confirm upcoming appointments and help patients cancel if needed",
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(contact_full_name=call.get_variable("patient_name"))


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    patient_name = call.get_variable("patient_name")
    appointment_id = call.get_variable("appointment_id")

    if outcome == "unavailable":
        call.hangup(
            final_instructions=(
                f"Leave a brief voicemail for {patient_name} from Metro Specialty Clinic "
                "asking them to confirm or cancel their upcoming appointment by calling back. "
                "Be brief and friendly."
            )
        )
    elif outcome == "available":
        try:
            token = get_access_token()
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            appointment = get_appointment(appointment_id, headers)
            logging.info("Appointment %s loaded from NextGen.", appointment_id)
        except Exception as e:
            logging.error("Failed to load appointment %s: %s", appointment_id, e)
            appointment = None
            headers = {}

        call.set_variable("appointment", appointment)
        call.set_variable("headers", headers)

        if not appointment:
            call.hangup(
                final_instructions=(
                    f"Let {patient_name} know you're calling from Metro Specialty Clinic "
                    "to confirm their appointment, but you couldn't retrieve the details. "
                    "Ask them to call the office. Be apologetic."
                )
            )
            return

        start = appointment.get("start", "")
        appt_type_coding = appointment.get("appointmentType", {}).get("coding", [])
        appt_type = appt_type_coding[0].get("display", "appointment") if appt_type_coding else "appointment"

        provider = ""
        for p in appointment.get("participant", []):
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

        call.set_task(
            "appointment_confirmation",
            objective=f"Confirm {patient_name}'s {appt_type} with {provider} on {display_time}.",
            checklist=[
                guava.Say(
                    f"Hi {patient_name}, this is Morgan calling from Metro Specialty Clinic. "
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
        )


@agent.on_task_complete("appointment_confirmation")
def on_appointment_confirmation_done(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    appointment_id = call.get_variable("appointment_id")
    attendance = call.get_field("attendance") or ""

    # Reconstruct appt_type and display_time from stored appointment data
    appointment = call.get_variable("appointment")
    appt_type = "appointment"
    if appointment:
        appt_type_coding = appointment.get("appointmentType", {}).get("coding", [])
        appt_type = appt_type_coding[0].get("display", "appointment") if appt_type_coding else "appointment"
        start = appointment.get("start", "")
        try:
            dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            display_time = dt.strftime("%A, %B %-d at %-I:%M %p")
        except (ValueError, AttributeError):
            display_time = start or "your upcoming appointment"
    else:
        display_time = "your upcoming appointment"

    if "cancel" in attendance:
        try:
            cancelled = cancel_appointment(appointment_id, call.get_variable("headers"))
            logging.info("Appointment %s cancelled: %s", appointment_id, cancelled)
        except Exception as e:
            logging.error("Cancel failed: %s", e)
        call.hangup(
            final_instructions=(
                f"Let {patient_name} know their {appt_type} has been cancelled. "
                "Invite them to call back or go online to reschedule. Wish them a great day."
            )
        )
    elif "reschedule" in attendance:
        call.hangup(
            final_instructions=(
                f"Let {patient_name} know a scheduling coordinator will call them back "
                "with new available times. Thank them for letting us know."
            )
        )
    else:
        logging.info("Appointment %s confirmed by %s.", appointment_id, patient_name)
        call.hangup(
            final_instructions=(
                f"Thank {patient_name} for confirming. Remind them to arrive a few minutes "
                "early and bring their insurance card and photo ID. Wish them a great day."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(description="Outbound appointment confirmation via NextGen FHIR.")
    parser.add_argument("phone", help="Patient phone number (E.164)")
    parser.add_argument("--name", required=True)
    parser.add_argument("--appointment-id", required=True)
    args = parser.parse_args()

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "patient_name": args.name,
            "appointment_id": args.appointment_id,
        },
    )
