import guava
import os
import logging
from guava import logging_utils
import json
import argparse
from datetime import datetime


agent = guava.Agent(
    name="Jordan",
    organization="Bright Smile Dental",
    purpose=(
        "to remind patients of their upcoming dental appointments, "
        "confirm attendance, and assist with rescheduling if needed"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(contact_full_name=call.get_variable("patient_name"))


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    if outcome == "unavailable":
        call.hangup(
            final_instructions=(
                "We were unable to reach the patient. Leave a brief, friendly voicemail on behalf "
                "of Bright Smile Dental asking them to call back to confirm or reschedule their "
                f"appointment on {call.get_variable('appointment')}. Provide the office number if available."
            )
        )
    elif outcome == "available":
        patient_name = call.get_variable("patient_name")
        appointment = call.get_variable("appointment")
        call.set_task(
            "reminder",
            objective=(
                f"Remind {patient_name} of their dental appointment at Bright Smile Dental "
                f"scheduled for {appointment}. Confirm whether they will attend or need to "
                "reschedule. If rescheduling is needed, collect their preferred day and time. "
                "Be friendly, professional, and concise."
            ),
            checklist=[
                guava.Say(
                    f"Hi {patient_name}, this is Jordan calling from Bright Smile Dental. "
                    f"I'm reaching out to confirm your upcoming appointment scheduled for {appointment}."
                ),
                guava.Say(
                    "We want to make sure we have you on the schedule and that the time still works for you."
                ),
                guava.Field(
                    key="appointment_confirmed",
                    description=(
                        "Ask the patient whether they confirm their appointment or need to reschedule. "
                        "Acceptable responses: 'confirm' or 'reschedule'."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="reschedule_requested",
                    description=(
                        "If the patient wants to reschedule, ask for their preferred day and time "
                        "for the new appointment. Only collect this if they said they need to reschedule."
                    ),
                    field_type="text",
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("reminder")
def on_done(call: guava.Call) -> None:
    results = {
        "timestamp": datetime.now().isoformat(),
        "patient_name": call.get_variable("patient_name"),
        "appointment": call.get_variable("appointment"),
        "appointment_confirmed": call.get_field("appointment_confirmed"),
        "reschedule_requested": call.get_field("reschedule_requested"),
    }
    print(json.dumps(results, indent=2))
    logging.info("Appointment reminder results saved.")

    confirmed = call.get_field("appointment_confirmed")
    if confirmed and confirmed.strip().lower() == "reschedule":
        call.hangup(
            final_instructions=(
                "Thank the patient for letting us know. Let them know that a team member from "
                "Bright Smile Dental will follow up shortly to confirm a new appointment time. "
                "Wish them a great day."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                "Thank the patient for confirming their appointment. Remind them to arrive "
                "10 minutes early to complete any necessary paperwork, and let them know we "
                "look forward to seeing them. Wish them a great day."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound appointment reminder call for Bright Smile Dental."
    )
    parser.add_argument("phone", help="Patient phone number to call")
    parser.add_argument("--name", required=True, help="Full name of the patient")
    parser.add_argument(
        "--appointment",
        default="tomorrow at 2:00 PM",
        help="Appointment datetime string (default: 'tomorrow at 2:00 PM')",
    )
    args = parser.parse_args()

    logging.info(
        "Initiating appointment reminder call to %s (%s) for appointment: %s",
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
