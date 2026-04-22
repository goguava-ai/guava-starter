import guava
import os
import logging
import json
import argparse
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)


class BenefitsEnrollmentController(guava.CallController):
    def __init__(self, resident_name: str, program_name: str, eligibility_reason: str):
        super().__init__()
        self.resident_name = resident_name
        self.program_name = program_name
        self.eligibility_reason = eligibility_reason
        self.set_persona(
            organization_name="City of Springfield - Community Services",
            agent_name="Jordan",
            agent_purpose=(
                f"inform eligible residents about {self.program_name} and guide them "
                "through initial enrollment questions"
            ),
        )
        self.reach_person(
            contact_full_name=self.resident_name,
            on_success=self.begin_enrollment,
            on_failure=self.recipient_unavailable,
        )

    def begin_enrollment(self):
        self.set_task(
            objective=(
                f"You are calling on behalf of the City of Springfield Community Services "
                f"department to inform {self.resident_name} that they may be eligible for "
                f"{self.program_name}. The reason they may qualify is: {self.eligibility_reason}. "
                "Briefly explain the program, then walk through the enrollment questions in a "
                "helpful and neutral public-service tone. Let the resident know their answers "
                "will be used only to determine eligibility and enrollment preferences."
            ),
            checklist=[
                guava.Say(
                    f"Hello, I'm calling from the City of Springfield Community Services "
                    f"department. We're reaching out because you may be eligible for "
                    f"{self.program_name}. The reason you may qualify is: {self.eligibility_reason}. "
                    "I have a few quick questions to help us understand your situation and "
                    "enrollment preferences. This should only take a couple of minutes."
                ),
                guava.Field(
                    key="interested_in_enrolling",
                    description="Ask whether the resident is interested in learning more about or enrolling in the program.",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="household_size",
                    description="Ask for the total number of people currently living in the resident's household.",
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="annual_household_income_range",
                    description=(
                        "Ask the resident to describe their approximate annual household income range "
                        "(e.g., under $20,000, $20,000–$40,000, $40,000–$60,000, over $60,000)."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="currently_receiving_benefits",
                    description=(
                        "Ask whether the resident is currently receiving any government assistance "
                        "or benefits programs, and if so, which ones."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="program_questions",
                    description=(
                        "Ask if the resident has any questions about the program before proceeding."
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="preferred_enrollment_method",
                    description=(
                        "Ask how the resident would prefer to complete enrollment: "
                        "online, by phone, or in person."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="best_callback_time",
                    description=(
                        "Ask if there is a preferred time for a follow-up call or appointment, "
                        "if one is needed."
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
            "resident_name": self.resident_name,
            "program_name": self.program_name,
            "eligibility_reason": self.eligibility_reason,
            "fields": {
                "interested_in_enrolling": self.get_field("interested_in_enrolling"),
                "household_size": self.get_field("household_size"),
                "annual_household_income_range": self.get_field("annual_household_income_range"),
                "currently_receiving_benefits": self.get_field("currently_receiving_benefits"),
                "program_questions": self.get_field("program_questions"),
                "preferred_enrollment_method": self.get_field("preferred_enrollment_method"),
                "best_callback_time": self.get_field("best_callback_time"),
            },
        }
        print(json.dumps(results, indent=2))
        self.hangup(
            final_instructions=(
                "Thank the resident for their time. Let them know that a Community Services "
                "representative will follow up with next steps based on their enrollment preference. "
                "Remind them they can also call the City of Springfield Community Services office "
                "directly with any questions. Wish them a good day and end the call politely."
            )
        )

    def recipient_unavailable(self):
        logging.info(
            "Resident %s was unavailable for benefits enrollment call regarding %s.",
            self.resident_name,
            self.program_name,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Outbound benefits enrollment call for City of Springfield Community Services."
    )
    parser.add_argument("phone", help="Resident phone number to call (E.164 format).")
    parser.add_argument("--name", required=True, help="Full name of the resident.")
    parser.add_argument(
        "--program-name",
        required=True,
        help='Name of the benefits program (e.g., "the Utility Assistance Program").',
    )
    parser.add_argument(
        "--eligibility-reason",
        required=True,
        help="Brief explanation of why the resident may qualify for the program.",
    )
    args = parser.parse_args()

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=BenefitsEnrollmentController(
            resident_name=args.name,
            program_name=args.program_name,
            eligibility_reason=args.eligibility_reason,
        ),
    )
