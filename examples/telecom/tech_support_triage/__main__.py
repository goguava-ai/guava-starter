import guava
import os
import logging
import json
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)


class TechSupportTriageController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Nexus Mobile - Technical Support",
            agent_name="Casey",
            agent_purpose=(
                "to greet customers calling in with technical issues, collect structured "
                "troubleshooting information to create an accurate support ticket, and "
                "ensure they are connected with the right technician as quickly as possible"
            ),
        )

        self.set_task(
            objective=(
                "A customer has called Nexus Mobile Technical Support. Greet them warmly, "
                "collect all the information needed to open a complete support ticket, "
                "and let them know a technician will be in touch. Be patient, clear, "
                "and professional throughout the call."
            ),
            checklist=[
                guava.Say(
                    "Thank you for calling Nexus Mobile Technical Support. My name is Casey "
                    "and I'm here to help you today. I'll be collecting some information so "
                    "we can get the right technician working on your issue as quickly as possible."
                ),
                guava.Field(
                    key="caller_name",
                    description="Ask the caller for their full name.",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="account_number",
                    description=(
                        "Ask the caller for their Nexus Mobile account number. "
                        "If they do not have it handy, ask for the phone number on the account."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="device_model",
                    description=(
                        "Ask the caller what device they are experiencing issues with — "
                        "including the make and model if possible (e.g. iPhone 15 Pro, "
                        "Samsung Galaxy S24, etc.)."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="issue_category",
                    description=(
                        "Ask the caller to describe what type of issue they are experiencing. "
                        "Based on their answer, categorize it as one of: no_signal, slow_data, "
                        "call_quality, billing, device_hardware, or other. "
                        "Capture the category label."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="issue_description",
                    description=(
                        "Ask the caller to describe the issue in their own words. "
                        "Capture a clear and detailed description of what is happening."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="issue_started",
                    description=(
                        "Ask the caller when they first noticed the issue — today, yesterday, "
                        "or how many days ago. Capture the timeframe they describe."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="already_rebooted",
                    description=(
                        "Ask the caller if they have already tried rebooting or restarting "
                        "their device since the issue began. Capture yes or no and any "
                        "relevant context they share."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="technician_callback_number",
                    description=(
                        "Ask the caller for the best phone number for a technician to reach "
                        "them on for a callback. Confirm the number back to them."
                    ),
                    field_type="text",
                    required=True,
                ),
            ],
            on_complete=self.save_results,
        )

        self.accept_call()

    def save_results(self):
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": "Casey",
            "organization": "Nexus Mobile - Technical Support",
            "use_case": "tech_support_triage",
            "fields": {
                "caller_name": self.get_field("caller_name"),
                "account_number": self.get_field("account_number"),
                "device_model": self.get_field("device_model"),
                "issue_category": self.get_field("issue_category"),
                "issue_description": self.get_field("issue_description"),
                "issue_started": self.get_field("issue_started"),
                "already_rebooted": self.get_field("already_rebooted"),
                "technician_callback_number": self.get_field("technician_callback_number"),
            },
        }
        print(json.dumps(results, indent=2))
        logging.info("Tech support triage ticket saved.")
        self.hangup(
            final_instructions=(
                "Let the customer know that their support ticket has been created and provide "
                "them with a ticket number (you may use a placeholder such as 'TKT-XXXXXX'). "
                "Inform them that a Nexus Mobile technician will call them back within 2 to 4 "
                "business hours at the number they provided. Thank them for calling and wish "
                "them a good day."
            )
        )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=TechSupportTriageController,
    )
