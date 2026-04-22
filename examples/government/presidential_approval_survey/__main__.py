import guava
import os
import logging
from guava import logging_utils
import json
from datetime import datetime


TO_NUMBER = "+13142239451"


class PollsterController(guava.CallController):
    def __init__(self):
        super().__init__()
        self.set_persona(
            organization_name="American Public Opinion Research",
            agent_name="Alex",
            agent_purpose=(
                "You are conducting a brief nonpartisan presidential approval survey "
                "on behalf of American Public Opinion Research, a nonprofit polling organization. "
                "Be neutral, professional, and respectful at all times."
            ),
        )
        self.conduct_survey()

    def conduct_survey(self):
        self.set_task(
            objective=(
                "Conduct a brief nonpartisan presidential approval phone survey. "
                "Start by introducing yourself and asking if the respondent has about two minutes "
                "to answer a few questions. If they decline, thank them and end the call politely. "
                "Ask each question in a neutral, unbiased manner without editorializing."
            ),
            checklist=[
                "Introduce yourself as Alex from American Public Opinion Research and ask "
                "if the respondent has about two minutes to answer a few survey questions about "
                "the current presidential administration.",
                guava.Field(
                    key="presidential_approval",
                    description=(
                        "Overall, do you approve, disapprove, or have no opinion of the job "
                        "the president is currently doing?"
                    ),
                    field_type="text",
                ),
                guava.Field(
                    key="economic_approval",
                    description=(
                        "Do you approve, disapprove, or have no opinion of the president's "
                        "handling of the economy?"
                    ),
                    field_type="text",
                ),
                guava.Field(
                    key="foreign_policy_approval",
                    description=(
                        "Do you approve, disapprove, or have no opinion of the president's "
                        "handling of foreign policy and national security?"
                    ),
                    field_type="text",
                ),
                guava.Field(
                    key="healthcare_approval",
                    description=(
                        "Do you approve, disapprove, or have no opinion of the president's "
                        "handling of healthcare policy?"
                    ),
                    field_type="text",
                ),
                guava.Field(
                    key="most_important_issue",
                    description=(
                        "In your opinion, what is the single most important issue facing "
                        "the country right now?"
                    ),
                    field_type="text",
                ),
                guava.Field(
                    key="party_affiliation",
                    description=(
                        "For demographic purposes, would you describe your political affiliation "
                        "as Democrat, Republican, Independent, or something else? "
                        "You are welcome to decline to answer."
                    ),
                    field_type="text",
                    required=False,
                ),
                "Thank the respondent sincerely for their time and participation in the survey.",
            ],
            on_complete=self.save_results,
        )

    def save_results(self):
        results = {
            "timestamp": datetime.now().isoformat(),
            "presidential_approval": self.get_field("presidential_approval"),
            "economic_approval": self.get_field("economic_approval"),
            "foreign_policy_approval": self.get_field("foreign_policy_approval"),
            "healthcare_approval": self.get_field("healthcare_approval"),
            "most_important_issue": self.get_field("most_important_issue"),
            "party_affiliation": self.get_field("party_affiliation"),
        }
        print("\n=== Survey Results ===")
        print(json.dumps(results, indent=2))
        self.hangup(
            final_instructions="Thank the respondent warmly for their participation and say goodbye."
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    client = guava.Client()
    client.create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=TO_NUMBER,
        call_controller=PollsterController(),
    )
