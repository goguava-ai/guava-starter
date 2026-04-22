import guava
import os
import logging
from guava import logging_utils
import json
import argparse
from datetime import datetime, timezone


agent = guava.Agent(
    name="Morgan",
    organization="Hargrove & Associates Law Firm",
    purpose=(
        "to proactively inform the client of the current status of their "
        "legal matter, confirm they understand the update and the next steps, "
        "and capture any questions they would like relayed to their attorney"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(contact_full_name=call.get_variable("contact_name"))


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    if outcome == "unavailable":
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "call_type": "outbound_client_status_update",
            "status": "recipient_unavailable",
            "meta": {
                "contact_name": call.get_variable("contact_name"),
                "matter_number": call.get_variable("matter_number"),
                "status_update": call.get_variable("status_update"),
                "next_step": call.get_variable("next_step"),
            },
        }
        print(json.dumps(results, indent=2))
        logging.info("Recipient unavailable for status update call.")
        call.hangup(
            final_instructions=(
                "Leave a brief, professional voicemail identifying yourself as Morgan "
                "calling from Hargrove and Associates Law Firm. State that you are "
                f"calling with a status update on matter number {call.get_variable('matter_number')} "
                "and ask that they return your call at their earliest convenience or "
                "visit the client portal for the latest information. Provide the "
                "firm's main number and say goodbye."
            )
        )
    elif outcome == "available":
        call.set_task(
            "status_update",
            objective=(
                f"Deliver a case status update to the client for matter number "
                f"{call.get_variable('matter_number')}. The current status is: {call.get_variable('status_update')}. "
                f"The next step is: {call.get_variable('next_step')}. Confirm the client understands "
                "both the update and the next step, capture any questions they have "
                "for their attorney, and note their preferred callback time if they "
                "would like to speak with someone directly."
            ),
            checklist=[
                guava.Say(
                    f"Good day. I am calling from Hargrove and Associates Law Firm "
                    f"with an update regarding matter number {call.get_variable('matter_number')}. "
                    f"Here is the current status: {call.get_variable('status_update')}. "
                    f"Regarding next steps: {call.get_variable('next_step')}. "
                    "I want to make sure you have all the information you need and "
                    "give you an opportunity to pass along any questions to your attorney."
                ),
                guava.Field(
                    key="update_understood",
                    description=(
                        "Confirmation that the client has heard and understood the "
                        "status update that was just provided"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="questions_for_attorney",
                    description=(
                        "Any questions the client would like relayed to their attorney, "
                        "noted verbatim where possible"
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="next_step_acknowledged",
                    description=(
                        "Confirmation that the client understands and acknowledges "
                        "the next step described in the update"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="preferred_callback_time",
                    description=(
                        "If the client would like to speak directly with their attorney "
                        "or a staff member, their preferred day and time for a callback"
                    ),
                    field_type="text",
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("status_update")
def on_done(call: guava.Call) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "call_type": "outbound_client_status_update",
        "meta": {
            "contact_name": call.get_variable("contact_name"),
            "matter_number": call.get_variable("matter_number"),
            "status_update": call.get_variable("status_update"),
            "next_step": call.get_variable("next_step"),
        },
        "fields": {
            "update_understood": call.get_field("update_understood"),
            "questions_for_attorney": call.get_field("questions_for_attorney"),
            "next_step_acknowledged": call.get_field("next_step_acknowledged"),
            "preferred_callback_time": call.get_field("preferred_callback_time"),
        },
    }
    print(json.dumps(results, indent=2))
    logging.info("Client status update results saved.")
    call.hangup(
        final_instructions=(
            "Thank the client by name for their time. If they provided questions "
            "for their attorney, assure them those will be passed along promptly. "
            "If they requested a callback, confirm that their preferred time has "
            "been noted. Remind them that Hargrove and Associates is committed to "
            "keeping them informed throughout their matter and that they are always "
            "welcome to contact the firm with questions. Say goodbye professionally."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound client status update call — Hargrove & Associates"
    )
    parser.add_argument("phone", help="Recipient phone number to dial")
    parser.add_argument("--name", required=True, help="Full name of the client")
    parser.add_argument("--matter-number", required=True, help="Matter or case number")
    parser.add_argument(
        "--status-update",
        required=True,
        help="Text describing the current status of the matter",
    )
    parser.add_argument(
        "--next-step",
        required=True,
        help="Text describing the next step or action in the matter",
    )
    args = parser.parse_args()

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "contact_name": args.name,
            "matter_number": args.matter_number,
            "status_update": args.status_update,
            "next_step": args.next_step,
        },
    )
