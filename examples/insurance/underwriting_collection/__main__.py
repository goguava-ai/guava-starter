import guava
import os
import logging
import json
import argparse
from datetime import datetime

logging.basicConfig(level=logging.INFO)


class UnderwritingCollectionController(guava.CallController):
    def __init__(self, contact_name: str, application_number: str):
        super().__init__()
        self.contact_name = contact_name
        self.application_number = application_number

        self.set_persona(
            organization_name="Keystone Property & Casualty - Underwriting",
            agent_name="Casey",
            agent_purpose=(
                "to collect supplemental property and risk information required to "
                "complete the underwriting review for a new policy application"
            ),
        )
        self.reach_person(
            contact_full_name=self.contact_name,
            on_success=self.start_underwriting_flow,
            on_failure=self.recipient_unavailable,
        )

    def start_underwriting_flow(self):
        self.set_task(
            objective=(
                f"You are calling {self.contact_name} regarding their new policy application "
                f"number {self.application_number}. The underwriting team requires additional "
                "property details before the application can be finalized. Collect information "
                "about the year the property was built, roof replacement history, security "
                "systems, prior claims within the last five years, and any features that may "
                "affect risk such as a trampoline or pool. Be professional and explain that "
                "this information helps ensure accurate and fair coverage."
            ),
            checklist=[
                guava.Say(
                    f"Hello {self.contact_name}, this is Casey calling from the Underwriting "
                    f"department at Keystone Property & Casualty. I'm reaching out about your "
                    f"policy application number {self.application_number}. Our underwriting "
                    "team needs a few additional details about the property before we can "
                    "finalize your coverage. This should only take a few minutes."
                ),
                guava.Field(
                    key="property_year_built",
                    description="The year the property was originally built",
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="roof_last_replaced",
                    description=(
                        "The year or approximate timeframe when the roof was last replaced "
                        "or significantly repaired"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="security_system_installed",
                    description=(
                        "Whether a monitored security or burglar alarm system is installed "
                        "at the property, and if so, the monitoring provider if known"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="prior_claims_last_5_years",
                    description=(
                        "The number of insurance claims filed against any property or auto "
                        "policy within the last five years"
                    ),
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="prior_claim_description",
                    description=(
                        "A brief description of prior claims if any were reported, "
                        "including type of claim and approximate settlement"
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="trampoline_or_pool",
                    description=(
                        "Whether the property has a trampoline, swimming pool, hot tub, "
                        "or other recreational features that may affect liability coverage"
                    ),
                    field_type="text",
                    required=True,
                ),
            ],
            on_complete=self.save_results,
        )

    def save_results(self):
        results = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "use_case": "underwriting_collection",
            "contact_name": self.contact_name,
            "application_number": self.application_number,
            "property_year_built": self.get_field("property_year_built"),
            "roof_last_replaced": self.get_field("roof_last_replaced"),
            "security_system_installed": self.get_field("security_system_installed"),
            "prior_claims_last_5_years": self.get_field("prior_claims_last_5_years"),
            "prior_claim_description": self.get_field("prior_claim_description"),
            "trampoline_or_pool": self.get_field("trampoline_or_pool"),
        }
        print(json.dumps(results, indent=2))
        logging.info("Underwriting collection results saved: %s", results)
        self.hangup(
            final_instructions=(
                "Thank you for your time, and for providing that information. Our underwriting "
                "team will review your application and the details you've shared. You can expect "
                "to hear back from us within two to three business days regarding the status of "
                "your application. If you have any questions in the meantime, please don't "
                "hesitate to contact Keystone Property & Casualty. Have a great day."
            )
        )

    def recipient_unavailable(self):
        logging.warning(
            "Could not reach %s for underwriting collection on application %s.",
            self.contact_name,
            self.application_number,
        )
        results = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "use_case": "underwriting_collection",
            "contact_name": self.contact_name,
            "application_number": self.application_number,
            "outcome": "recipient_unavailable",
        }
        print(json.dumps(results, indent=2))
        self.hangup(
            final_instructions=(
                "We were unable to reach the applicant. "
                "Please schedule a follow-up call to complete underwriting collection."
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Outbound underwriting data collection call for Keystone Property & Casualty"
    )
    parser.add_argument("phone", help="Phone number to dial")
    parser.add_argument("--name", required=True, help="Full name of the applicant")
    parser.add_argument(
        "--application-number", required=True, help="Policy application number"
    )
    args = parser.parse_args()

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=UnderwritingCollectionController(
            contact_name=args.name,
            application_number=args.application_number,
        ),
    )
