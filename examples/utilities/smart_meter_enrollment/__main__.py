import guava
import os
import logging
from guava import logging_utils
import json
import argparse
from datetime import datetime



class SmartMeterEnrollmentController(guava.CallController):
    def __init__(self, contact_name, account_number):
        super().__init__()
        self.contact_name = contact_name
        self.account_number = account_number

        self.set_persona(
            organization_name="Metro Power & Light",
            agent_name="Jordan",
            agent_purpose=(
                "explain the benefits of the smart meter upgrade program to eligible customers "
                "and schedule a convenient installation appointment for those who wish to enroll"
            ),
        )

        self.reach_person(
            contact_full_name=self.contact_name,
            on_success=self.begin_enrollment,
            on_failure=self.recipient_unavailable,
        )

    def begin_enrollment(self):
        self.set_task(
            objective=(
                f"Speak with {self.contact_name} (account {self.account_number}) about enrolling "
                "in the Metro Power & Light smart meter upgrade program. Explain that smart meters "
                "provide real-time usage data, eliminate estimated bills, enable remote meter reading "
                "so no one needs to enter the property, and unlock access to energy usage tools "
                "through the online portal. Ask if they would like to schedule a free installation "
                "appointment and, if so, collect their scheduling preferences."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.contact_name.split()[0]}, I'm calling from Metro Power & Light about "
                    f"an exciting upgrade available for your account. Your home is eligible for our "
                    f"free smart meter installation. Smart meters give you real-time visibility into "
                    f"your energy usage, eliminate estimated bills, and mean our technicians no longer "
                    f"need to access your property for monthly readings. The installation takes about "
                    f"30 minutes and is completely free of charge."
                ),
                guava.Field(
                    key="enrollment_accepted",
                    description="Ask the customer whether they would like to enroll and schedule a free smart meter installation appointment",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="installation_date_preference",
                    description="Ask what date works best for the customer's smart meter installation appointment",
                    field_type="date",
                    required=True,
                ),
                guava.Field(
                    key="installation_window_preference",
                    description="Ask whether the customer prefers a morning window (8 AM to 12 PM), an afternoon window (12 PM to 5 PM), or if any time works for the installation",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="pets_to_secure",
                    description="Ask whether the customer has any pets that will need to be secured or kept away from the technician on the day of installation",
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="gate_code_or_access_notes",
                    description="Ask if there is a gate code or any special access instructions the technician will need to reach the meter on installation day",
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
            "account_number": self.account_number,
            "status": "recipient_unavailable",
        }
        print(json.dumps(results, indent=2))
        self.hangup(
            final_instructions=(
                "Leave a brief, friendly voicemail letting the customer know that Metro Power & Light "
                "called regarding their eligibility for a free smart meter upgrade. Ask them to call "
                "back at their convenience or visit metropowerandlight.com to learn more and schedule "
                "online. Keep the message under 30 seconds."
            )
        )

    def save_results(self):
        results = {
            "timestamp": datetime.now().isoformat(),
            "contact_name": self.contact_name,
            "account_number": self.account_number,
            "fields": {
                "enrollment_accepted": self.get_field("enrollment_accepted"),
                "installation_date_preference": self.get_field("installation_date_preference"),
                "installation_window_preference": self.get_field("installation_window_preference"),
                "pets_to_secure": self.get_field("pets_to_secure"),
                "gate_code_or_access_notes": self.get_field("gate_code_or_access_notes"),
            },
        }
        print(json.dumps(results, indent=2))
        self.hangup(
            final_instructions=(
                "Confirm the appointment details back to the customer, including the date and time window. "
                "Let them know they will receive a confirmation email or text, and that a technician will "
                "call 30 minutes before arriving. Thank them for choosing to upgrade and for being a "
                "Metro Power & Light customer."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Metro Power & Light — Smart Meter Enrollment Outbound Call"
    )
    parser.add_argument("phone", help="Customer phone number to call")
    parser.add_argument("--name", required=True, help="Customer full name")
    parser.add_argument("--account-number", required=True, help="Customer account number")
    args = parser.parse_args()

    controller = SmartMeterEnrollmentController(
        contact_name=args.name,
        account_number=args.account_number,
    )

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=controller,
    )
