import guava
import os
import logging
from guava import logging_utils
import json
import argparse
import requests
from datetime import datetime, timezone


agent = guava.Agent(
    name="Jordan",
    organization="Evergreen Family Clinic",
    purpose=(
        "to confirm upcoming patient appointments, assist with rescheduling "
        "if needed, and ensure the clinic schedule stays accurate"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(contact_full_name=call.get_variable("patient_name"))


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    if outcome == "unavailable":
        appointment = call.get_variable("appointment")
        call.hangup(
            final_instructions=(
                "We were unable to reach the patient. Leave a brief, friendly voicemail "
                "from Evergreen Family Clinic asking them to call back to confirm or "
                f"reschedule their appointment on {appointment}. Provide the clinic "
                "phone number if available."
            )
        )
    elif outcome == "available":
        patient_name = call.get_variable("patient_name")
        appointment = call.get_variable("appointment")
        call.set_task(
            "save_results",
            objective=(
                f"You've reached {patient_name}. Confirm their upcoming appointment at "
                f"Evergreen Family Clinic scheduled for {appointment}. If they need to "
                "reschedule, collect their preferred date and time. Be warm and professional."
            ),
            checklist=[
                guava.Say(
                    f"Hi {patient_name}, this is Jordan calling from Evergreen Family Clinic. "
                    f"I'm reaching out to confirm your appointment scheduled for {appointment}."
                ),
                guava.Field(
                    key="appointment_confirmed",
                    description=(
                        "Ask the patient whether they confirm their appointment or need to "
                        "reschedule. Capture 'confirmed' or 'reschedule'."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="preferred_date",
                    description=(
                        "If the patient needs to reschedule, ask for their preferred date. "
                        "Only collect this if they said they need to reschedule."
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="preferred_time",
                    description=(
                        "If the patient needs to reschedule, ask for their preferred time of day "
                        "(morning, afternoon, or a specific time). Only collect if rescheduling."
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="reason_for_change",
                    description=(
                        "If the patient is rescheduling, ask briefly why they need to change. "
                        "Capture the reason. Only collect if rescheduling."
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="additional_notes",
                    description=(
                        "Ask if there's anything else the clinic should know before their visit — "
                        "new symptoms, insurance changes, etc. Capture any notes."
                    ),
                    field_type="text",
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("save_results")
def on_done(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    appointment = call.get_variable("appointment")

    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": "Jordan",
        "organization": "Evergreen Family Clinic",
        "use_case": "outbound_appointment_confirmation",
        "patient_name": patient_name,
        "appointment": appointment,
        "fields": {
            "appointment_confirmed": call.get_field("appointment_confirmed"),
            "preferred_date": call.get_field("preferred_date"),
            "preferred_time": call.get_field("preferred_time"),
            "reason_for_change": call.get_field("reason_for_change"),
            "additional_notes": call.get_field("additional_notes"),
        },
    }
    print(json.dumps(results, indent=2))
    logging.info("Appointment confirmation results saved locally.")

    # Push task to Webex Contact Center
    try:
        base_url = os.environ["WEBEX_CC_BASE_URL"]
        token = os.environ["WEBEX_CC_ACCESS_TOKEN"]
        org_id = os.environ["WEBEX_CC_ORG_ID"]
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        confirmed = call.get_field("appointment_confirmed", "")
        if confirmed.strip().lower() == "reschedule":
            task_title = f"Reschedule appointment for {patient_name}"
        else:
            task_title = f"Appointment confirmed for {patient_name}"

        task_payload = {
            "orgId": org_id,
            "title": task_title,
            "description": json.dumps({
                "patient_name": patient_name,
                "original_appointment": appointment,
                "appointment_confirmed": call.get_field("appointment_confirmed"),
                "preferred_date": call.get_field("preferred_date"),
                "preferred_time": call.get_field("preferred_time"),
                "reason_for_change": call.get_field("reason_for_change"),
                "additional_notes": call.get_field("additional_notes"),
            }),
            "channel": "voice",
            "source": "guava_voice_agent",
        }
        resp = requests.post(
            f"{base_url}/v1/contactCenter/tasks",
            headers=headers,
            json=task_payload,
            timeout=10,
        )
        resp.raise_for_status()
        logging.info("Webex CC task created successfully.")
    except Exception as e:
        logging.error("Failed to push to Webex CC: %s", e)

    confirmed = call.get_field("appointment_confirmed", "")
    if confirmed.strip().lower() == "reschedule":
        call.hangup(
            final_instructions=(
                "Thank the patient for letting us know. Let them know that someone from "
                "Evergreen Family Clinic will call back to confirm a new appointment time "
                "based on their preference. Wish them a great day."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                "Thank the patient for confirming. Remind them to arrive 10 minutes early "
                "and to bring their insurance card and a photo ID. Let them know we look "
                "forward to seeing them. Wish them a great day."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound appointment confirmation call for Evergreen Family Clinic."
    )
    parser.add_argument("phone", help="Patient phone number to call")
    parser.add_argument("--name", required=True, help="Full name of the patient")
    parser.add_argument(
        "--appointment",
        default="tomorrow at 10:00 AM",
        help="Appointment datetime string (default: 'tomorrow at 10:00 AM')",
    )
    args = parser.parse_args()

    logging.info(
        "Initiating appointment confirmation call to %s (%s) for appointment: %s",
        args.name,
        args.phone,
        args.appointment,
    )

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "patient_name": args.name,
            "appointment": args.appointment,
        },
    )
