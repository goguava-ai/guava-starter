import guava
import os
import logging
from guava import logging_utils
import json
import argparse
from datetime import datetime



class CourseFeedbackController(guava.CallController):
    def __init__(self, name, course_name, instructor_name, term):
        super().__init__()
        self.name = name
        self.course_name = course_name
        self.instructor_name = instructor_name
        self.term = term
        self.set_persona(
            organization_name="Westfield University - Academic Affairs",
            agent_name="Sam",
            agent_purpose=(
                "gather structured post-term feedback from students on their course "
                "and instructor experience to help improve academic quality"
            ),
        )
        self.reach_person(
            contact_full_name=self.name,
            on_success=self.begin_course_feedback,
            on_failure=self.recipient_unavailable,
        )

    def begin_course_feedback(self):
        self.set_task(
            objective=(
                f"You are calling {self.name} to collect feedback on the course "
                f"'{self.course_name}' taught by {self.instructor_name} during the {self.term} term. "
                "Gather numeric ratings on a scale of 1 to 5 for overall course quality, the instructor, "
                "and course difficulty. Also capture open-ended responses about what the student found "
                "most valuable, what could be improved, and whether they would recommend the course "
                "to other students. Be friendly and assure the student their feedback is anonymous "
                "and genuinely valued."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.name}, this is Sam from Westfield University Academic Affairs. "
                    f"Now that the {self.term} term has wrapped up, we're reaching out to students "
                    f"to collect feedback on their courses. I'd love to get your thoughts on "
                    f"'{self.course_name}' with {self.instructor_name} — it should only take a couple "
                    "of minutes, and your responses are kept confidential."
                ),
                guava.Field(
                    key="course_overall_rating",
                    description=(
                        f"The student's overall rating of '{self.course_name}' on a scale of 1 to 5, "
                        "where 1 is poor and 5 is excellent"
                    ),
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="instructor_rating",
                    description=(
                        f"The student's rating of instructor {self.instructor_name} on a scale of 1 to 5, "
                        "where 1 is poor and 5 is excellent"
                    ),
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="course_difficulty_rating",
                    description=(
                        f"The student's rating of how difficult they found '{self.course_name}' "
                        "on a scale of 1 to 5, where 1 is very easy and 5 is very difficult"
                    ),
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="most_valuable_aspect",
                    description=f"The aspect of '{self.course_name}' the student found most valuable or memorable",
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="suggested_improvements",
                    description=f"Any improvements or changes the student would suggest for '{self.course_name}'",
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="would_recommend_course",
                    description=f"Whether the student would recommend '{self.course_name}' to other students, and any context they provide",
                    field_type="text",
                    required=True,
                ),
            ],
            on_complete=self.save_results,
        )

    def save_results(self):
        results = {
            "timestamp": datetime.now().isoformat(),
            "student_name": self.name,
            "course_name": self.course_name,
            "instructor_name": self.instructor_name,
            "term": self.term,
            "fields": {
                "course_overall_rating": self.get_field("course_overall_rating"),
                "instructor_rating": self.get_field("instructor_rating"),
                "course_difficulty_rating": self.get_field("course_difficulty_rating"),
                "most_valuable_aspect": self.get_field("most_valuable_aspect"),
                "suggested_improvements": self.get_field("suggested_improvements"),
                "would_recommend_course": self.get_field("would_recommend_course"),
            },
        }
        print(json.dumps(results, indent=2))
        self.hangup(
            final_instructions=(
                f"Thank {self.name} sincerely for taking the time to share their feedback. "
                "Let them know their input genuinely helps Westfield University improve the "
                "student experience. Wish them the best for the upcoming term and say goodbye warmly."
            )
        )

    def recipient_unavailable(self):
        logging.info(
            "Could not reach %s for course feedback on '%s' (%s).",
            self.name,
            self.course_name,
            self.term,
        )
        results = {
            "timestamp": datetime.now().isoformat(),
            "student_name": self.name,
            "course_name": self.course_name,
            "instructor_name": self.instructor_name,
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
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Post-term course feedback call to collect student ratings and comments"
    )
    parser.add_argument("phone", help="Phone number to call (e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Full name of the student")
    parser.add_argument("--course-name", required=True, help="Name of the course being evaluated")
    parser.add_argument(
        "--instructor-name",
        required=True,
        help="Full name of the course instructor",
    )
    parser.add_argument(
        "--term",
        required=True,
        help="Academic term being evaluated (e.g. 'Fall 2025')",
    )
    args = parser.parse_args()

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=CourseFeedbackController(
            name=args.name,
            course_name=args.course_name,
            instructor_name=args.instructor_name,
            term=args.term,
        ),
    )
