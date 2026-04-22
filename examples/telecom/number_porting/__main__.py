import guava
import os
import logging
from guava import logging_utils
import json
import argparse
from datetime import datetime, timezone


agent = guava.Agent(
    name="Morgan",
    organization="Nexus Mobile - Porting Team",
    purpose=(
        "to coordinate with customers who are in the process of porting their phone "
        "number to Nexus Mobile, confirm the accuracy of their porting details, "
        "collect any missing account information from their previous carrier, "
        "and set clear expectations about the port completion timeline"
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
            "agent": "Morgan",
            "organization": "Nexus Mobile - Porting Team",
            "use_case": "number_porting",
            "contact_name": call.get_variable("contact_name"),
            "new_account_number": call.get_variable("new_account_number"),
            "number_being_ported": call.get_variable("number_being_ported"),
            "status": "recipient_unavailable",
        }
        print(json.dumps(results, indent=2))
        logging.info("Recipient unavailable for number porting coordination call.")
        call.hangup(
            final_instructions=(
                "The contact was not available. End the call politely. Do not leave "
                "sensitive porting details such as account numbers or PINs in a voicemail."
            )
        )
    elif outcome == "available":
        contact_name = call.get_variable("contact_name")
        new_account_number = call.get_variable("new_account_number")
        number_being_ported = call.get_variable("number_being_ported")
        expected_port_date = call.get_variable("expected_port_date")
        call.set_task(
            "porting_flow",
            objective=(
                f"You are speaking with {contact_name}, who is in the process of porting "
                f"their number {number_being_ported} to Nexus Mobile "
                f"(new account #{new_account_number}). "
                f"The expected port completion date is {expected_port_date}. "
                "Your goal is to verify the porting details are correct, collect the previous "
                "carrier account number and PIN which are required to complete the port, "
                "confirm the authorized contact name on the old account, and ensure the "
                "customer understands what to expect. Be efficient, clear, and reassuring."
            ),
            checklist=[
                guava.Say(
                    f"Hi {contact_name.split()[0]}, this is Morgan calling from the Nexus Mobile "
                    f"Porting Team. I'm calling regarding the transfer of your phone number "
                    f"ending in {number_being_ported[-4:]} to your new Nexus Mobile account. "
                    f"I have just a few quick items to go over to make sure everything goes "
                    f"smoothly on your port date."
                ),
                guava.Field(
                    key="porting_details_confirmed",
                    description=(
                        f"Confirm with the customer that the number being ported is "
                        f"{number_being_ported} and that their new Nexus Mobile account number "
                        f"is {new_account_number}. Ask if these details are correct. "
                        "Capture their confirmation or any corrections they provide."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="previous_carrier_account_number",
                    description=(
                        "Explain that to complete the port, Nexus Mobile needs the account number "
                        "from the customer's previous carrier. Ask them to provide that account number. "
                        "Capture it exactly as they state it."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="previous_carrier_pin",
                    description=(
                        "Ask the customer for the account PIN or transfer PIN associated with "
                        "their previous carrier account. Explain this is required by the previous "
                        "carrier to authorize the port. Capture the PIN they provide."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="authorized_contact_name",
                    description=(
                        "Ask the customer for the name of the authorized account holder on the "
                        "previous carrier account — this must match the name on file with the "
                        "previous carrier. Capture the full name they provide."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="port_completion_date_acknowledged",
                    description=(
                        f"Inform the customer that their number is expected to port on "
                        f"{expected_port_date}. Explain that during the brief porting window "
                        "their service will transfer automatically and they may experience a short "
                        "interruption. Ask if they acknowledge and understand the expected date. "
                        "Capture their response."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="questions_about_porting",
                    description=(
                        "Ask if the customer has any questions about the porting process, "
                        "the timeline, or what to expect on port day. Capture any questions "
                        "they ask and the answers provided."
                    ),
                    field_type="text",
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("porting_flow")
def on_done(call: guava.Call) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": "Morgan",
        "organization": "Nexus Mobile - Porting Team",
        "use_case": "number_porting",
        "contact_name": call.get_variable("contact_name"),
        "new_account_number": call.get_variable("new_account_number"),
        "number_being_ported": call.get_variable("number_being_ported"),
        "expected_port_date": call.get_variable("expected_port_date"),
        "fields": {
            "porting_details_confirmed": call.get_field("porting_details_confirmed"),
            "previous_carrier_account_number": call.get_field("previous_carrier_account_number"),
            "previous_carrier_pin": call.get_field("previous_carrier_pin"),
            "authorized_contact_name": call.get_field("authorized_contact_name"),
            "port_completion_date_acknowledged": call.get_field("port_completion_date_acknowledged"),
            "questions_about_porting": call.get_field("questions_about_porting"),
        },
    }
    print(json.dumps(results, indent=2))
    logging.info("Number porting coordination call results saved.")
    call.hangup(
        final_instructions=(
            "Thank the customer for providing their information. Reassure them that their "
            "porting request is on track and that the Nexus Mobile Porting Team will handle "
            "the rest. Remind them of the expected port date and let them know they can call "
            "Nexus Mobile if they have any concerns before then. Wish them well."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Nexus Mobile — Number Porting coordination outbound call agent"
    )
    parser.add_argument("phone", help="Customer phone number to call (E.164 format)")
    parser.add_argument("--name", required=True, help="Full name of the customer")
    parser.add_argument(
        "--new-account-number", required=True, help="Customer's new Nexus Mobile account number"
    )
    parser.add_argument(
        "--number-being-ported", required=True, help="The phone number being ported to Nexus Mobile"
    )
    parser.add_argument(
        "--expected-port-date", required=True, help="Expected date for port completion (e.g. March 1, 2026)"
    )
    args = parser.parse_args()

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "contact_name": args.name,
            "new_account_number": args.new_account_number,
            "number_being_ported": args.number_being_ported,
            "expected_port_date": args.expected_port_date,
        },
    )
