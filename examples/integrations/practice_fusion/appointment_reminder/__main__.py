import argparse
import logging
import os
from datetime import datetime

import guava
import requests
from guava import logging_utils

BASE_URL = os.environ.get("PRACTICE_FUSION_FHIR_BASE_URL", "https://api.practicefusion.com/fhir/r4")


def get_headers():
    return {
        "Authorization": f"Bearer {os.environ['PRACTICE_FUSION_ACCESS_TOKEN']}",
        "Content-Type": "application/json",
    }


def get_appointment(appointment_id: str) -> dict:
    """Fetch a single Appointment resource by ID."""
    resp = requests.get(
        f"{BASE_URL}/Appointment/{appointment_id}",
        headers=get_headers(),
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def patch_appointment(appointment_id: str, status: str, cancellation_reason: str | None = None) -> dict:
    """Update the status (and optionally cancellation comment) on an Appointment resource."""
    payload: dict = {
        "resourceType": "Appointment",
        "id": appointment_id,
        "status": status,
    }
    if cancellation_reason:
        payload["comment"] = f"Patient cancellation reason: {cancellation_reason}"
    resp = requests.patch(
        f"{BASE_URL}/Appointment/{appointment_id}",
        headers=get_headers(),
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def format_appointment_start(appointment: dict) -> str:
    """Return a human-readable date/time string for the appointment's start time."""
    start_str = appointment.get("start", "")
    try:
        dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
        return dt.strftime("%A, %B %-d at %-I:%M %p")
    except (ValueError, AttributeError):
        return start_str or "your upcoming appointment"


def get_provider_display(appointment: dict) -> str:
    """Return the display name of the practitioner participant, if present."""
    for participant in appointment.get("participant", []):
        actor = participant.get("actor", {})
        ref = actor.get("reference", "")
        if ref.startswith("Practitioner"):
            return actor.get("display", "")
    return ""


agent = guava.Agent(
    name="Taylor",
    organization="Riverside Family Medicine",
    purpose=(
        "to remind patients of their upcoming appointments at Riverside Family Medicine "
        "and record whether they plan to attend or need to cancel"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    call.reach_person(contact_full_name=patient_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    patient_name = call.get_variable("patient_name")
    appointment_id = call.get_variable("appointment_id")

    if outcome == "unavailable":
        appointment_description = "the scheduled date"
        try:
            appointment = get_appointment(appointment_id)
            appointment_description = format_appointment_start(appointment)
        except Exception:
            pass
        call.hangup(
            final_instructions=(
                f"Leave a brief, friendly voicemail for {patient_name} on behalf of Riverside "
                f"Family Medicine reminding them of their appointment on "
                f"{appointment_description}. "
                "Ask them to call the office back if they have questions or need to reschedule. "
                "Do not leave any clinical details in the voicemail. Keep it under 30 seconds."
            )
        )
    elif outcome == "available":
        appointment_description = "your upcoming appointment"
        provider_name = ""
        try:
            appointment = get_appointment(appointment_id)
            appointment_description = format_appointment_start(appointment)
            provider_name = get_provider_display(appointment)
            logging.info(
                "Appointment %s: %s with %s",
                appointment_id,
                appointment_description,
                provider_name or "provider",
            )
        except Exception as exc:
            logging.error("Failed to fetch appointment %s: %s", appointment_id, exc)

        provider_clause = f" with {provider_name}" if provider_name else ""

        call.set_task(
            "deliver_reminder",
            objective=(
                f"Remind {patient_name} of their appointment{provider_clause} at Riverside Family Medicine "
                f"on {appointment_description}. Confirm whether they plan to attend or need to cancel."
            ),
            checklist=[
                guava.Say(
                    f"Hello {patient_name}, this is Taylor calling from Riverside Family Medicine. "
                    f"I'm reaching out to remind you of your appointment{provider_clause} scheduled for "
                    f"{appointment_description}."
                ),
                guava.Field(
                    key="confirmed",
                    field_type="multiple_choice",
                    description=(
                        "Ask whether the patient plans to keep their appointment or needs to cancel it. "
                        "Capture their response."
                    ),
                    choices=["confirm", "cancel"],
                    required=True,
                ),
                guava.Field(
                    key="cancellation_reason",
                    field_type="text",
                    description=(
                        "If the patient chose to cancel, ask for a brief reason "
                        "(e.g., scheduling conflict, feeling better, transportation issue). "
                        "Only collect this field if they said they need to cancel."
                    ),
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("deliver_reminder")
def on_done(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    appointment_id = call.get_variable("appointment_id")

    confirmed = call.get_field("confirmed")
    cancellation_reason = call.get_field("cancellation_reason")

    cancelled = confirmed and confirmed.strip().lower() == "cancel"
    new_status = "cancelled" if cancelled else "booked"

    # Post-call: patch the appointment status in Practice Fusion.
    # For cancellations, include the patient-provided reason as a comment.
    try:
        patch_appointment(
            appointment_id,
            new_status,
            cancellation_reason if cancelled else None,
        )
        logging.info(
            "Appointment %s patched to status=%s",
            appointment_id,
            new_status,
        )
    except Exception as exc:
        logging.error("Failed to patch appointment %s: %s", appointment_id, exc)

    if cancelled:
        call.hangup(
            final_instructions=(
                f"Let {patient_name} know their appointment has been cancelled and that "
                "a member of the Riverside Family Medicine scheduling team will follow up to "
                "help them find a new time whenever they are ready. Thank them warmly."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {patient_name} for confirming. Let them know we look forward to "
                "seeing them. Remind them to arrive about 10 minutes early and to bring a photo "
                "ID and insurance card if they have not visited recently. Wish them a great day."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound appointment reminder call for Riverside Family Medicine via Practice Fusion FHIR R4."
    )
    parser.add_argument("phone", help="Patient phone number in E.164 format (e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Patient full name")
    parser.add_argument("--patient-id", required=True, help="Practice Fusion FHIR Patient resource ID")
    parser.add_argument("--appointment-id", required=True, help="Practice Fusion FHIR Appointment resource ID")
    args = parser.parse_args()

    logging.info(
        "Initiating appointment reminder call to %s (%s), appointment %s",
        args.name,
        args.phone,
        args.appointment_id,
    )

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "patient_name": args.name,
            "patient_id": args.patient_id,
            "appointment_id": args.appointment_id,
        },
    )
