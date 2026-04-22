import argparse
import json
import logging
import os
from datetime import datetime, timezone

import guava
from guava import logging_utils

agent = guava.Agent(
    name="Casey",
    organization="Keystone Property & Casualty - Underwriting",
    purpose=(
        "to collect supplemental property and risk information required to "
        "complete the underwriting review for a new policy application"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(contact_full_name=call.get_variable("contact_name"))


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    if outcome == "unavailable":
        logging.warning(
            "Could not reach %s for underwriting collection on application %s.",
            call.get_variable("contact_name"),
            call.get_variable("application_number"),
        )
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "use_case": "underwriting_collection",
            "contact_name": call.get_variable("contact_name"),
            "application_number": call.get_variable("application_number"),
            "outcome": "recipient_unavailable",
        }
        print(json.dumps(results, indent=2))
        call.hangup(
            final_instructions=(
                "We were unable to reach the applicant. "
                "Please schedule a follow-up call to complete underwriting collection."
            )
        )
    elif outcome == "available":
        call.set_task(
            "underwriting_collection",
            objective=(
                f"You are calling {call.get_variable('contact_name')} regarding their new policy application "
                f"number {call.get_variable('application_number')}. The underwriting team requires additional "
                "property details before the application can be finalized. Collect information "
                "about the year the property was built, roof replacement history, security "
                "systems, prior claims within the last five years, and any features that may "
                "affect risk such as a trampoline or pool. Be professional and explain that "
                "this information helps ensure accurate and fair coverage."
            ),
            checklist=[
                guava.Say(
                    f"Hello {call.get_variable('contact_name')}, this is Casey calling from the Underwriting "
                    f"department at Keystone Property & Casualty. I'm reaching out about your "
                    f"policy application number {call.get_variable('application_number')}. Our underwriting "
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
        )


@agent.on_task_complete("underwriting_collection")
def on_done(call: guava.Call) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "use_case": "underwriting_collection",
        "contact_name": call.get_variable("contact_name"),
        "application_number": call.get_variable("application_number"),
        "property_year_built": call.get_field("property_year_built"),
        "roof_last_replaced": call.get_field("roof_last_replaced"),
        "security_system_installed": call.get_field("security_system_installed"),
        "prior_claims_last_5_years": call.get_field("prior_claims_last_5_years"),
        "prior_claim_description": call.get_field("prior_claim_description"),
        "trampoline_or_pool": call.get_field("trampoline_or_pool"),
    }
    print(json.dumps(results, indent=2))
    logging.info("Underwriting collection results saved: %s", results)
    call.hangup(
        final_instructions=(
            "Thank you for your time, and for providing that information. Our underwriting "
            "team will review your application and the details you've shared. You can expect "
            "to hear back from us within two to three business days regarding the status of "
            "your application. If you have any questions in the meantime, please don't "
            "hesitate to contact Keystone Property & Casualty. Have a great day."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound underwriting data collection call for Keystone Property & Casualty"
    )
    parser.add_argument("phone", help="Phone number to dial")
    parser.add_argument("--name", required=True, help="Full name of the applicant")
    parser.add_argument(
        "--application-number", required=True, help="Policy application number"
    )
    args = parser.parse_args()

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "contact_name": args.name,
            "application_number": args.application_number,
        },
    )
