import guava
import os
import logging
from guava import logging_utils
import json
import argparse
from datetime import datetime, timezone



class PublicHealthSurveyController(guava.CallController):
    def __init__(self):
        super().__init__()
        self.set_persona(
            organization_name="Springfield County Public Health Department",
            agent_name="Alex",
            agent_purpose=(
                "conduct a brief anonymous public health survey to gather "
                "epidemiological data for the Springfield County community"
            ),
        )
        self.set_task(
            objective=(
                "You are calling on behalf of the Springfield County Public Health Department "
                "to conduct a short, voluntary, and anonymous health survey. The purpose is to "
                "gather epidemiological data to help the county understand the health status "
                "of the community and improve public health programs. Assure respondents that "
                "no personally identifying information will be recorded and participation is "
                "entirely voluntary. Be respectful, neutral, and brief."
            ),
            checklist=[
                guava.Say(
                    "Hello, this is Alex calling from the Springfield County Public Health "
                    "Department. We are conducting a brief, voluntary, and anonymous community "
                    "health survey. Your responses help us understand the health needs of our "
                    "community and improve local public health programs. This survey takes "
                    "approximately two to three minutes. No personally identifying information "
                    "will be recorded. Would you be willing to participate?"
                ),
                guava.Field(
                    key="household_count",
                    description="Ask how many people, including the respondent, currently live in their household.",
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="vaccinations_up_to_date",
                    description=(
                        "Ask whether the respondent believes the vaccinations for people in "
                        "their household are generally up to date, including routine immunizations."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="flu_shot_this_season",
                    description=(
                        "Ask whether anyone in the household has received a flu shot during "
                        "the current flu season."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="chronic_conditions_present",
                    description=(
                        "Ask, in general terms, whether anyone in the household manages a "
                        "chronic health condition such as diabetes, heart disease, asthma, "
                        "or a similar ongoing condition. Responses can be general — "
                        "no specific diagnoses are required."
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="healthcare_access_barriers",
                    description=(
                        "Ask whether anyone in the household has experienced difficulty "
                        "accessing healthcare in the past year, such as cost, transportation, "
                        "wait times, or availability of providers."
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="health_insurance_status",
                    description=(
                        "Ask whether all members of the household currently have health "
                        "insurance coverage of some kind."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="primary_care_physician_assigned",
                    description=(
                        "Ask whether the household members have an assigned primary care "
                        "physician or regular healthcare provider they see for routine care."
                    ),
                    field_type="text",
                    required=True,
                ),
            ],
            on_complete=self.save_results,
        )

    def save_results(self):
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "survey_type": "public_health_survey",
            "organization": "Springfield County Public Health Department",
            "fields": {
                "household_count": self.get_field("household_count"),
                "vaccinations_up_to_date": self.get_field("vaccinations_up_to_date"),
                "flu_shot_this_season": self.get_field("flu_shot_this_season"),
                "chronic_conditions_present": self.get_field("chronic_conditions_present"),
                "healthcare_access_barriers": self.get_field("healthcare_access_barriers"),
                "health_insurance_status": self.get_field("health_insurance_status"),
                "primary_care_physician_assigned": self.get_field("primary_care_physician_assigned"),
            },
        }
        print(json.dumps(results, indent=2))
        self.hangup(
            final_instructions=(
                "Thank the respondent sincerely for participating in the survey. Let them know "
                "their responses contribute to improving public health services in Springfield County. "
                "Remind them that all responses are anonymous. If they have questions about local "
                "public health resources, encourage them to visit the Springfield County Public "
                "Health Department website or call the department directly. End the call politely."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound public health survey call for Springfield County Public Health Department."
    )
    parser.add_argument("phone", help="Resident phone number to call (E.164 format).")
    args = parser.parse_args()

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=PublicHealthSurveyController(),
    )
