import guava
import os
import logging
import json
import argparse
from datetime import datetime

logging.basicConfig(level=logging.INFO)


class EnrollmentFollowupController(guava.CallController):
    def __init__(self, name, student_id, missing_items, term):
        super().__init__()
        self.name = name
        self.student_id = student_id
        self.missing_items = missing_items
        self.term = term
        self.set_persona(
            organization_name="Westfield University - Enrollment Services",
            agent_name="Jordan",
            agent_purpose=(
                "follow up with students who have incomplete enrollment paperwork "
                "and help them understand what is missing and how to submit it"
            ),
        )
        self.reach_person(
            contact_full_name=self.name,
            on_success=self.begin_enrollment_followup,
            on_failure=self.recipient_unavailable,
        )

    def begin_enrollment_followup(self):
        self.set_task(
            objective=(
                f"You are following up with {self.name} (student ID: {self.student_id}) "
                f"regarding incomplete enrollment paperwork for the {self.term} term. "
                f"The following items are still missing or incomplete: {self.missing_items}. "
                "Inform the student clearly, confirm they understand what is needed, "
                "find out how they plan to submit the missing items and by when, "
                "confirm they are still planning to start the upcoming term, "
                "and address any questions they may have about the enrollment process."
            ),
            checklist=[
                guava.Say(
                    f"Hello {self.name}, I'm calling from Westfield University Enrollment Services "
                    f"regarding your enrollment for {self.term}. We show that your file is missing "
                    f"the following: {self.missing_items}. We want to make sure we get everything "
                    "sorted out so your enrollment is complete."
                ),
                guava.Field(
                    key="missing_info_acknowledged",
                    description="Confirm the student acknowledges what information or documents are missing from their enrollment file",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="info_submission_method",
                    description=(
                        "How the student plans to submit the missing information or documents. "
                        "Options are: online_portal, email, or in_person"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="submission_date_commitment",
                    description="The date by which the student commits to submitting the missing items",
                    field_type="date",
                    required=True,
                ),
                guava.Field(
                    key="term_start_confirmed",
                    description=f"Whether the student confirms they are still planning to enroll and start the {self.term} term",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="questions_about_enrollment",
                    description="Any questions or concerns the student has about the enrollment process",
                    field_type="text",
                    required=False,
                ),
            ],
            on_complete=self.save_results,
        )

    def save_results(self):
        results = {
            "timestamp": datetime.now().isoformat(),
            "student_name": self.name,
            "student_id": self.student_id,
            "missing_items": self.missing_items,
            "term": self.term,
            "fields": {
                "missing_info_acknowledged": self.get_field("missing_info_acknowledged"),
                "info_submission_method": self.get_field("info_submission_method"),
                "submission_date_commitment": self.get_field("submission_date_commitment"),
                "term_start_confirmed": self.get_field("term_start_confirmed"),
                "questions_about_enrollment": self.get_field("questions_about_enrollment"),
            },
        }
        print(json.dumps(results, indent=2))
        self.hangup(
            final_instructions=(
                f"Thank {self.name} for their time. Let them know that Enrollment Services "
                "is happy to help if they have any further questions and wish them a great start "
                f"to the {self.term} term. Say goodbye warmly."
            )
        )

    def recipient_unavailable(self):
        logging.info(
            "Could not reach %s for enrollment follow-up (student ID: %s).",
            self.name,
            self.student_id,
        )
        results = {
            "timestamp": datetime.now().isoformat(),
            "student_name": self.name,
            "student_id": self.student_id,
            "missing_items": self.missing_items,
            "term": self.term,
            "outcome": "recipient_unavailable",
        }
        print(json.dumps(results, indent=2))
        self.hangup(
            final_instructions=(
                "The student could not be reached. End the call politely."
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Enrollment follow-up call for students with incomplete paperwork"
    )
    parser.add_argument("phone", help="Phone number to call (e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Full name of the student")
    parser.add_argument("--student-id", required=True, help="Student ID number")
    parser.add_argument(
        "--missing-items",
        required=True,
        help="Description of what enrollment items are incomplete",
    )
    parser.add_argument(
        "--term",
        required=True,
        help="Enrollment term (e.g. 'Fall 2026')",
    )
    args = parser.parse_args()

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=EnrollmentFollowupController(
            name=args.name,
            student_id=args.student_id,
            missing_items=args.missing_items,
            term=args.term,
        ),
    )
