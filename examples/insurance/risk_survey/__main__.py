import guava
import os
import logging
import json
import argparse
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)


class RiskSurveyController(guava.CallController):
    def __init__(self, contact_name: str, policy_number: str):
        super().__init__()
        self.contact_name = contact_name
        self.policy_number = policy_number

        self.set_persona(
            organization_name="Keystone Property & Casualty - Risk Assessment",
            agent_name="Sam",
            agent_purpose=(
                "to schedule a property inspection appointment and collect pre-inspection "
                "risk information to help the inspector prepare for their visit"
            ),
        )
        self.reach_person(
            contact_full_name=self.contact_name,
            on_success=self.start_risk_survey_flow,
            on_failure=self.recipient_unavailable,
        )

    def start_risk_survey_flow(self):
        self.set_task(
            objective=(
                f"You are calling {self.contact_name} regarding policy number "
                f"{self.policy_number} to coordinate a property inspection and gather "
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
                    f"Hi {self.contact_name}, this is Sam calling from the Risk Assessment "
                    f"team at Keystone Property & Casualty regarding your policy number "
                    f"{self.policy_number}. We'd like to schedule a routine property "
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
            on_complete=self.save_results,
        )

    def save_results(self):
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "use_case": "risk_survey_and_inspection_scheduling",
            "contact_name": self.contact_name,
            "policy_number": self.policy_number,
            "inspection_date_preference": self.get_field("inspection_date_preference"),
            "access_instructions": self.get_field("access_instructions"),
            "dogs_on_property": self.get_field("dogs_on_property"),
            "renovation_in_progress": self.get_field("renovation_in_progress"),
            "electrical_panel_age": self.get_field("electrical_panel_age"),
            "hvac_age": self.get_field("hvac_age"),
        }
        print(json.dumps(results, indent=2))
        logging.info("Risk survey results saved: %s", results)
        self.hangup(
            final_instructions=(
                "Thank you so much for your time and for sharing that information. Our team "
                "will confirm your inspection appointment date by email and you will receive "
                "a reminder the day before the visit. The inspector will arrive during the "
                "agreed window and the inspection typically takes about thirty to forty-five "
                "minutes. If anything changes or you need to reschedule, please contact "
                "Keystone Property & Casualty at your earliest convenience. Have a great day."
            )
        )

    def recipient_unavailable(self):
        logging.warning(
            "Could not reach %s for risk survey on policy %s.",
            self.contact_name,
            self.policy_number,
        )
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "use_case": "risk_survey_and_inspection_scheduling",
            "contact_name": self.contact_name,
            "policy_number": self.policy_number,
            "outcome": "recipient_unavailable",
        }
        print(json.dumps(results, indent=2))
        self.hangup(
            final_instructions=(
                "We were unable to reach the insured. "
                "Please follow up to schedule the property inspection."
            )
        )


if __name__ == "__main__":
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

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=RiskSurveyController(
            contact_name=args.name,
            policy_number=args.policy_number,
        ),
    )
