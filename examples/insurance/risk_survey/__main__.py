import argparse
import json
import logging
import os
from datetime import datetime, timezone

import guava
from guava import logging_utils

agent = guava.Agent(
    name="Sam",
    organization="Keystone Property & Casualty - Risk Assessment",
    purpose=(
        "to schedule a property inspection appointment and collect pre-inspection "
        "risk information to help the inspector prepare for their visit"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(contact_full_name=call.get_variable("contact_name"))


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    if outcome == "unavailable":
        logging.warning(
            "Could not reach %s for risk survey on policy %s.",
            call.get_variable("contact_name"),
            call.get_variable("policy_number"),
        )
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "use_case": "risk_survey_and_inspection_scheduling",
            "contact_name": call.get_variable("contact_name"),
            "policy_number": call.get_variable("policy_number"),
            "outcome": "recipient_unavailable",
        }
        print(json.dumps(results, indent=2))
        call.hangup(
            final_instructions=(
                "We were unable to reach the insured. "
                "Please follow up to schedule the property inspection."
            )
        )
    elif outcome == "available":
        call.set_task(
            "risk_survey",
            objective=(
                f"You are calling {call.get_variable('contact_name')} regarding policy number "
                f"{call.get_variable('policy_number')} to coordinate a property inspection and gather "
                "pre-inspection risk data. Collect their preferred inspection date, any "
                "access instructions for the inspector, and information about property "
                "conditions that affect the inspection or risk profile such as dogs on "
                "the premises, active renovations, and the approximate age of the "
                "electrical panel and HVAC system. Be friendly and explain that the "
                "inspection is a standard part of the policy process and helps ensure "
                "the coverage accurately reflects the property."
            ),
            checklist=[
                guava.Say(
                    f"Hi {call.get_variable('contact_name')}, this is Sam calling from the Risk Assessment "
                    f"team at Keystone Property & Casualty regarding your policy number "
                    f"{call.get_variable('policy_number')}. We'd like to schedule a routine property "
                    "inspection and I have a few quick questions to help our inspector "
                    "prepare for the visit."
                ),
                guava.Field(
                    key="inspection_date_preference",
                    description=(
                        "The insured's preferred date or date range for the property inspection"
                    ),
                    field_type="date",
                    required=True,
                ),
                guava.Field(
                    key="access_instructions",
                    description=(
                        "Any special instructions for the inspector to access the property, "
                        "such as gate codes, key lockbox location, or contact person on site"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="dogs_on_property",
                    description=(
                        "Whether there are dogs or other animals on the property that the "
                        "inspector should be aware of, including breed if a dog is present"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="renovation_in_progress",
                    description=(
                        "Whether any active renovations or construction work are currently "
                        "underway at the property, and a brief description if so"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="electrical_panel_age",
                    description=(
                        "The approximate age or last known replacement year of the main "
                        "electrical panel, if the insured knows it"
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="hvac_age",
                    description=(
                        "The approximate age or last known replacement year of the primary "
                        "HVAC system, if the insured knows it"
                    ),
                    field_type="text",
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("risk_survey")
def on_done(call: guava.Call) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "use_case": "risk_survey_and_inspection_scheduling",
        "contact_name": call.get_variable("contact_name"),
        "policy_number": call.get_variable("policy_number"),
        "inspection_date_preference": call.get_field("inspection_date_preference"),
        "access_instructions": call.get_field("access_instructions"),
        "dogs_on_property": call.get_field("dogs_on_property"),
        "renovation_in_progress": call.get_field("renovation_in_progress"),
        "electrical_panel_age": call.get_field("electrical_panel_age"),
        "hvac_age": call.get_field("hvac_age"),
    }
    print(json.dumps(results, indent=2))
    logging.info("Risk survey results saved: %s", results)
    call.hangup(
        final_instructions=(
            "Thank you so much for your time and for sharing that information. Our team "
            "will confirm your inspection appointment date by email and you will receive "
            "a reminder the day before the visit. The inspector will arrive during the "
            "agreed window and the inspection typically takes about thirty to forty-five "
            "minutes. If anything changes or you need to reschedule, please contact "
            "Keystone Property & Casualty at your earliest convenience. Have a great day."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description=(
            "Outbound risk survey and inspection scheduling call "
            "for Keystone Property & Casualty"
        )
    )
    parser.add_argument("phone", help="Phone number to dial")
    parser.add_argument("--name", required=True, help="Full name of the insured")
    parser.add_argument("--policy-number", required=True, help="Policy number")
    args = parser.parse_args()

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "contact_name": args.name,
            "policy_number": args.policy_number,
        },
    )
