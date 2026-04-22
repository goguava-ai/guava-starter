import argparse
import json
import os
from datetime import datetime

import guava
from guava import logging_utils

agent = guava.Agent(
    name="Casey",
    organization="Metro Power & Light - New Connections",
    purpose=(
        "coordinate new electric service activation appointments with customers who are "
        "moving into the Metro Power & Light service area, confirm their move-in details, "
        "and schedule a convenient connection date"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(contact_full_name=call.get_variable("contact_name"))


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    if outcome == "unavailable":
        results = {
            "timestamp": datetime.now().isoformat(),
            "contact_name": call.get_variable("contact_name"),
            "service_address": call.get_variable("service_address"),
            "application_number": call.get_variable("application_number"),
            "status": "recipient_unavailable",
        }
        print(json.dumps(results, indent=2))
        call.hangup(
            final_instructions=(
                "Leave a voicemail letting the customer know that Metro Power & Light New Connections "
                "called to schedule their electric service activation appointment for their upcoming "
                "move. Ask them to call back or visit metropowerandlight.com to schedule online, "
                "referencing their application number. Let them know scheduling promptly ensures "
                "power is ready on move-in day."
            )
        )
    elif outcome == "available":
        contact_name = call.get_variable("contact_name")
        service_address = call.get_variable("service_address")
        application_number = call.get_variable("application_number")
        call.set_task(
            "service_connection_scheduling",
            objective=(
                f"Speak with {contact_name} regarding their new service application "
                f"(application {application_number}) for the address at {service_address}. "
                "Confirm their move-in date, schedule a service connection appointment that works "
                "for their timeline, and verify billing details. Also offer optional programs "
                "such as autopay and paperless billing to help them get set up conveniently "
                "from the start."
            ),
            checklist=[
                guava.Say(
                    f"Hi {contact_name.split()[0]}, this is Casey calling from Metro Power & Light "
                    f"New Connections. I'm reaching out about your application to start electric service "
                    f"at {service_address} — application number {application_number}. "
                    f"I'd like to confirm a few details and get your connection appointment scheduled "
                    f"so your power is ready when you move in."
                ),
                guava.Field(
                    key="move_in_date",
                    description="Ask the customer what date they are planning to move in to the new address",
                    field_type="date",
                    required=True,
                ),
                guava.Field(
                    key="preferred_connection_date",
                    description="Ask what date the customer would like their electric service to be activated — this should typically be on or before their move-in date",
                    field_type="date",
                    required=True,
                ),
                guava.Field(
                    key="preferred_time_window",
                    description="Ask whether the customer prefers a morning connection window (8 AM to 12 PM), an afternoon window (12 PM to 5 PM), or if any time works",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="billing_address_confirmed",
                    description="Ask the customer to confirm whether their billing address will be the same as the service address, or if they have a different mailing address for their bills",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="autopay_interest",
                    description="Ask if the customer would like to enroll in autopay to have their monthly bill paid automatically, which also qualifies them for a small monthly discount",
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="paperless_billing_interest",
                    description="Ask if the customer would like to go paperless and receive their bills and account notifications by email instead of mail",
                    field_type="text",
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("service_connection_scheduling")
def on_done(call: guava.Call) -> None:
    results = {
        "timestamp": datetime.now().isoformat(),
        "contact_name": call.get_variable("contact_name"),
        "service_address": call.get_variable("service_address"),
        "application_number": call.get_variable("application_number"),
        "fields": {
            "move_in_date": call.get_field("move_in_date"),
            "preferred_connection_date": call.get_field("preferred_connection_date"),
            "preferred_time_window": call.get_field("preferred_time_window"),
            "billing_address_confirmed": call.get_field("billing_address_confirmed"),
            "autopay_interest": call.get_field("autopay_interest"),
            "paperless_billing_interest": call.get_field("paperless_billing_interest"),
        },
    }
    print(json.dumps(results, indent=2))
    call.hangup(
        final_instructions=(
            "Confirm the connection appointment date and time window back to the customer. "
            "Let them know that a technician will be on-site during the scheduled window to "
            "activate service, and that someone 18 or older must be present at the property. "
            "Mention they will receive a confirmation by email or text. Welcome them to Metro "
            "Power & Light and wish them well with their move."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Metro Power & Light New Connections — Service Activation Scheduling"
    )
    parser.add_argument("phone", help="Customer phone number to call")
    parser.add_argument("--name", required=True, help="Customer full name")
    parser.add_argument(
        "--service-address",
        required=True,
        help="Street address where service will be activated",
    )
    parser.add_argument(
        "--application-number",
        required=True,
        help="New service application number",
    )
    args = parser.parse_args()

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "contact_name": args.name,
            "service_address": args.service_address,
            "application_number": args.application_number,
        },
    )
