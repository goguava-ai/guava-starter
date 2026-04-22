import guava
import os
import logging
from guava import logging_utils
import json
import requests
import argparse
from datetime import datetime, timezone


agent = guava.Agent(
    name="Maya",
    organization="Cedar Health",
    purpose=(
        "to confirm or cancel upcoming appointments on behalf of Cedar Health "
        "and update the appointment record in Epic accordingly"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    appointment_id = call.get_variable("appointment_id")

    appointment_display = "your upcoming appointment"
    # Pre-call: fetch the appointment from Epic so the agent can speak the exact
    # date and time.
    try:
        base_url = os.environ["EPIC_BASE_URL"]
        access_token = os.environ["EPIC_ACCESS_TOKEN"]
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        resp = requests.get(
            f"{base_url}/Appointment/{appointment_id}",
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        appt = resp.json()
        start = appt.get("start", "")
        if start:
            # Format the ISO timestamp into a natural-language string for the agent to speak
            dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            appointment_display = dt.strftime("%A, %B %-d at %-I:%M %p")
    except Exception as e:
        logging.error("Failed to fetch Epic Appointment: %s", e)

    call.appointment_display = appointment_display
    call.reach_person(contact_full_name=patient_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    patient_name = call.get_variable("patient_name")
    if outcome == "unavailable":
        call.hangup(
            final_instructions=(
                "We were unable to reach the patient. Leave a brief voicemail on behalf of Cedar Health "
                f"asking them to call back to confirm or cancel their appointment on {call.appointment_display}."
            )
        )
    elif outcome == "available":
        call.set_task(
            "appointment_confirmation",
            objective=(
                f"Confirm or cancel {patient_name}'s appointment at Cedar Health "
                f"scheduled for {call.appointment_display}. Be warm, concise, and respectful."
            ),
            checklist=[
                guava.Say(
                    f"Hi {patient_name}, this is Maya calling from Cedar Health. "
                    f"I'm reaching out to confirm your appointment scheduled for {call.appointment_display}."
                ),
                guava.Field(
                    key="confirmation",
                    description=(
                        "Ask whether the patient will keep their appointment or needs to cancel. "
                        "Capture 'confirm' or 'cancel'."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="cancellation_reason",
                    description=(
                        "If the patient wants to cancel, ask for the reason. "
                        "Only collect this if they said they need to cancel."
                    ),
                    field_type="text",
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("appointment_confirmation")
def on_done(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    appointment_id = call.get_variable("appointment_id")
    confirmation = call.get_field("confirmation")
    cancellation_reason = call.get_field("cancellation_reason")

    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": "Maya",
        "organization": "Cedar Health",
        "use_case": "appointment_confirmation",
        "patient_name": patient_name,
        "appointment_id": appointment_id,
        "fields": {
            "confirmation": confirmation,
            "cancellation_reason": cancellation_reason,
        },
    }
    print(json.dumps(results, indent=2))
    logging.info("Appointment confirmation results saved locally.")

    # Post-call: patch the appointment status in Epic based on the patient's choice.
    # PATCH rather than PUT so we only touch the status field without overwriting
    # other appointment data. Cancellation reason is included in comment when provided.
    try:
        base_url = os.environ["EPIC_BASE_URL"]
        access_token = os.environ["EPIC_ACCESS_TOKEN"]
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        cancelled = confirmation and confirmation.strip().lower() == "cancel"
        new_status = "cancelled" if cancelled else "booked"

        patch_payload = {"resourceType": "Appointment", "id": appointment_id, "status": new_status}
        if cancelled and cancellation_reason:
            patch_payload["comment"] = f"Patient cancellation reason: {cancellation_reason}"

        resp = requests.patch(
            f"{base_url}/Appointment/{appointment_id}",
            headers=headers,
            json=patch_payload,
            timeout=10,
        )
        resp.raise_for_status()
        logging.info("Epic Appointment %s updated to status: %s", appointment_id, new_status)
    except Exception as e:
        logging.error("Failed to update Epic Appointment: %s", e)

    # Close the call with a message that matches the patient's outcome
    if confirmation and confirmation.strip().lower() == "cancel":
        call.hangup(
            final_instructions=(
                "Let the patient know their appointment has been cancelled and that Cedar Health "
                "will reach out to help them reschedule when they are ready. Thank them and "
                "wish them a great day."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                "Thank the patient for confirming. Remind them to arrive 10 minutes early "
                "and bring their insurance card and a valid photo ID. Wish them a great day."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound appointment confirmation call for Cedar Health via Epic FHIR."
    )
    parser.add_argument("phone", help="Patient phone number to call (E.164 format, e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Full name of the patient")
    parser.add_argument("--appointment-id", required=True, help="Epic Appointment FHIR resource ID")
    args = parser.parse_args()

    logging.info(
        "Initiating appointment confirmation call to %s (%s) for appointment %s",
        args.name,
        args.phone,
        args.appointment_id,
    )

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "patient_name": args.name,
            "appointment_id": args.appointment_id,
        },
    )
