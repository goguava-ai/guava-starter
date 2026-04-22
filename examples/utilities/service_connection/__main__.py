import guava
import os
import logging
from guava import logging_utils
import json
import argparse
from datetime import datetime



class ServiceConnectionController(guava.CallController):
    def __init__(self, contact_name, service_address, application_number):
        super().__init__()
        self.contact_name = contact_name
        self.service_address = service_address
        self.application_number = application_number

        self.set_persona(
            organization_name="Metro Power & Light - New Connections",
            agent_name="Casey",
            agent_purpose=(
                "coordinate new electric service activation appointments with customers who are "
                "moving into the Metro Power & Light service area, confirm their move-in details, "
                "and schedule a convenient connection date"
            ),
        )

        self.reach_person(
            contact_full_name=self.contact_name,
            on_success=self.begin_scheduling,
            on_failure=self.recipient_unavailable,
        )

    def begin_scheduling(self):
        self.set_task(
            objective=(
                f"Speak with {self.contact_name} regarding their new service application "
                f"(application {self.application_number}) for the address at {self.service_address}. "
                "Confirm their move-in date, schedule a service connection appointment that works "
                "for their timeline, and verify billing details. Also offer optional programs "
                "such as autopay and paperless billing to help them get set up conveniently "
                "from the start."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.contact_name.split()[0]}, this is Casey calling from Metro Power & Light "
                    f"New Connections. I'm reaching out about your application to start electric service "
                    f"at {self.service_address} — application number {self.application_number}. "
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
            on_complete=self.save_results,
        )

    def recipient_unavailable(self):
        results = {
            "timestamp": datetime.now().isoformat(),
            "contact_name": self.contact_name,
            "service_address": self.service_address,
            "application_number": self.application_number,
            "status": "recipient_unavailable",
        }
        print(json.dumps(results, indent=2))
        self.hangup(
            final_instructions=(
                "Leave a voicemail letting the customer know that Metro Power & Light New Connections "
                "called to schedule their electric service activation appointment for their upcoming "
                "move. Ask them to call back or visit metropowerandlight.com to schedule online, "
                "referencing their application number. Let them know scheduling promptly ensures "
                "power is ready on move-in day."
            )
        )

    def save_results(self):
        results = {
            "timestamp": datetime.now().isoformat(),
            "contact_name": self.contact_name,
            "service_address": self.service_address,
            "application_number": self.application_number,
            "fields": {
                "move_in_date": self.get_field("move_in_date"),
                "preferred_connection_date": self.get_field("preferred_connection_date"),
                "preferred_time_window": self.get_field("preferred_time_window"),
                "billing_address_confirmed": self.get_field("billing_address_confirmed"),
                "autopay_interest": self.get_field("autopay_interest"),
                "paperless_billing_interest": self.get_field("paperless_billing_interest"),
            },
        }
        print(json.dumps(results, indent=2))
        self.hangup(
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

    controller = ServiceConnectionController(
        contact_name=args.name,
        service_address=args.service_address,
        application_number=args.application_number,
    )

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=controller,
    )
