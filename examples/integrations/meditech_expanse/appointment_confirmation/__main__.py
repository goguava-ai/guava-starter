import argparse
import logging
import os
from datetime import datetime

import guava
import requests
from guava import logging_utils

FHIR_BASE_URL = os.environ["MEDITECH_FHIR_BASE_URL"]


def get_headers() -> dict:
    return {
        "Authorization": f"Bearer {os.environ['MEDITECH_ACCESS_TOKEN']}",
        "Content-Type": "application/json",
        "Accept": "application/fhir+json",
    }


def fetch_appointment(appointment_id: str) -> dict:
    """Fetch a single FHIR Appointment resource from Meditech Expanse."""
    resp = requests.get(
        f"{FHIR_BASE_URL}/Appointment/{appointment_id}",
        headers=get_headers(),
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def format_appointment_datetime(iso_str: str) -> str:
    """Return a human-readable appointment time string from an ISO 8601 timestamp."""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%A, %B %-d at %-I:%M %p")
    except (ValueError, AttributeError):
        return iso_str


def _update_appointment_status(appointment_id: str, new_status: str, cancellation_reason: str | None):
    """PATCH the Meditech FHIR Appointment resource to reflect the patient's decision."""
    patch_ops: list[dict] = [
        {"op": "replace", "path": "/status", "value": new_status}
    ]
    if cancellation_reason:
        patch_ops.append(
            {
                "op": "add",
                "path": "/cancelationReason",
                "value": {
                    "coding": [
                        {
                            "system": (
                                "http://terminology.hl7.org/CodeSystem/appointment-cancellation-reason"
                            ),
                            "display": cancellation_reason,
                        }
                    ],
                    "text": cancellation_reason,
                },
            }
        )

    try:
        resp = requests.patch(
            f"{FHIR_BASE_URL}/Appointment/{appointment_id}",
            headers={
                **get_headers(),
                "Content-Type": "application/json-patch+json",
            },
            json=patch_ops,
            timeout=10,
        )
        resp.raise_for_status()
        logging.info(
            "Appointment %s status updated to '%s' in Meditech.",
            appointment_id,
            new_status,
        )
    except Exception as e:
        logging.error(
            "Failed to update Appointment %s status in Meditech: %s",
            appointment_id,
            e,
        )


agent = guava.Agent(
    name="Jordan",
    organization="St. Raphael Medical Center",
    purpose=(
        "to confirm upcoming hospital appointments with patients and capture "
        "any cancellations or scheduling changes on their behalf"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    appointment_id = call.get_variable("appointment_id")

    appointment_display = "your upcoming appointment"
    appointment = None

    # Fetch the appointment so we can greet the patient with the correct details.
    try:
        appointment = fetch_appointment(appointment_id)
        start = appointment.get("start", "")
        service = (
            (appointment.get("serviceType") or [{}])[0]
            .get("text", "appointment")
        )
        appointment_display = (
            f"your {service} on {format_appointment_datetime(start)}"
        )
        logging.info(
            "Fetched appointment %s for patient %s: %s",
            appointment_id,
            call.get_variable("patient_id"),
            appointment_display,
        )
    except Exception as e:
        logging.error("Pre-fetch of appointment %s failed: %s", appointment_id, e)

    call.set_variable("appointment_display", appointment_display)

    call.reach_person(contact_full_name=patient_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    patient_name = call.get_variable("patient_name")
    appointment_display = call.get_variable("appointment_display") or "your upcoming appointment"

    if outcome == "unavailable":
        call.hangup(
            final_instructions=(
                f"Leave a brief, professional voicemail for {patient_name} on behalf of "
                "St. Raphael Medical Center. Let them know we called to confirm "
                f"{appointment_display}. Ask them to call us back at their earliest "
                "convenience to confirm or reschedule. Keep the message under 30 seconds."
            )
        )
    elif outcome == "available":
        call.set_task(
            "collect_confirmation",
            objective=(
                f"Confirm whether {patient_name} will be attending "
                f"{appointment_display} at St. Raphael Medical Center. "
                "If they cancel, capture the reason."
            ),
            checklist=[
                guava.Say(
                    f"Hi {patient_name}, this is Jordan calling from "
                    f"St. Raphael Medical Center. I'm reaching out to confirm "
                    f"{appointment_display}. Do you have a moment?"
                ),
                guava.Field(
                    key="confirmation_status",
                    description=(
                        "Ask whether the patient is confirming or cancelling their appointment. "
                        "Capture 'confirmed' if they plan to attend, or 'cancelled' if they do not."
                    ),
                    field_type="multiple_choice",
                    choices=["confirmed", "cancelled"],
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("collect_confirmation")
def handle_confirmation(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    appointment_id = call.get_variable("appointment_id")
    appointment_display = call.get_variable("appointment_display") or "your upcoming appointment"
    status = call.get_field("confirmation_status")

    if status and status.strip().lower() == "cancelled":
        # Patient is cancelling — collect the reason before updating Meditech.
        call.set_task(
            "collect_cancellation_reason",
            objective=(
                f"The patient has decided to cancel {appointment_display}. "
                "Collect the reason for the cancellation."
            ),
            checklist=[
                guava.Field(
                    key="cancellation_reason",
                    description=(
                        "Ask why the patient needs to cancel their appointment. "
                        "Options are: scheduling conflict, feeling better, transportation issue, "
                        "financial concern, or other."
                    ),
                    field_type="multiple_choice",
                    choices=[
                        "scheduling conflict",
                        "feeling better",
                        "transportation issue",
                        "financial concern",
                        "other",
                    ],
                    required=True,
                ),
            ],
        )
    else:
        # Patient confirmed — update the Appointment status to "booked" (already booked,
        # but we flip it to mark it as explicitly confirmed by the patient).
        _update_appointment_status(appointment_id, "booked", cancellation_reason=None)
        call.hangup(
            final_instructions=(
                f"Thank {patient_name} for confirming their appointment at "
                "St. Raphael Medical Center. Remind them to arrive 15 minutes early "
                "and to bring their insurance card and a valid photo ID. "
                "Let them know they can call us if anything changes. Wish them a great day."
            )
        )


@agent.on_task_complete("collect_cancellation_reason")
def process_cancellation(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    appointment_id = call.get_variable("appointment_id")
    appointment_display = call.get_variable("appointment_display") or "your upcoming appointment"
    reason = call.get_field("cancellation_reason")
    _update_appointment_status(appointment_id, "cancelled", cancellation_reason=reason)
    call.hangup(
        final_instructions=(
            f"Acknowledge {patient_name}'s cancellation and thank them for letting "
            "St. Raphael Medical Center know in advance. Let them know the appointment has "
            "been cancelled in our system. Encourage them to call us when they are ready to "
            "reschedule, and remind them that our scheduling line is available Monday through "
            "Friday, 8 AM to 5 PM. Wish them well."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description=(
            "Outbound appointment confirmation call for St. Raphael Medical Center "
            "via Meditech Expanse FHIR."
        )
    )
    parser.add_argument(
        "phone",
        help="Patient phone number to call (E.164 format, e.g. +15551234567)",
    )
    parser.add_argument("--name", required=True, help="Full name of the patient")
    parser.add_argument(
        "--patient-id",
        required=True,
        help="Meditech Expanse Patient FHIR resource ID",
    )
    parser.add_argument(
        "--appointment-id",
        required=True,
        help="Meditech Expanse Appointment FHIR resource ID to confirm",
    )
    args = parser.parse_args()

    logging.info(
        "Initiating appointment confirmation call to %s (%s), appointment ID: %s",
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
