import guava
import os
import logging
import json
import argparse
from datetime import datetime

logging.basicConfig(level=logging.INFO)


class AttendanceCheckinController(guava.CallController):
    def __init__(self, parent_name, student_name, absence_date, periods_missed):
        super().__init__()
        self.parent_name = parent_name
        self.student_name = student_name
        self.absence_date = absence_date
        self.periods_missed = periods_missed
        self.set_persona(
            organization_name="Westfield Elementary School - Attendance Office",
            agent_name="Casey",
            agent_purpose=(
                "contact parents and guardians when a student has an unexcused absence "
                "to collect a reason and ensure the family is aware"
            ),
        )
        self.reach_person(
            contact_full_name=self.parent_name,
            on_success=self.begin_attendance_checkin,
            on_failure=self.recipient_unavailable,
        )

    def begin_attendance_checkin(self):
        self.set_task(
            objective=(
                f"You are calling {self.parent_name}, the parent or guardian of {self.student_name}, "
                f"because {self.student_name} has an unexcused absence on {self.absence_date} "
                f"for {self.periods_missed}. "
                "Your goal is to collect the reason for the absence, find out if the student is expected "
                "to return, determine whether a doctor's note will be provided, confirm the parent is aware "
                "of the absence, and capture any message they would like passed along to the teacher."
            ),
            checklist=[
                guava.Say(
                    f"Hello {self.parent_name}, this is Casey calling from Westfield Elementary School's "
                    f"Attendance Office. I'm reaching out today because {self.student_name} was marked "
                    f"absent on {self.absence_date} for {self.periods_missed}, and we don't currently "
                    "have an excuse on file. I just wanted to check in and make sure everything is okay."
                ),
                guava.Field(
                    key="absence_reason",
                    description=(
                        f"The reason for {self.student_name}'s absence. "
                        "Options are: illness, family_emergency, appointment, other, or unknown"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="expected_return_date",
                    description=f"The date on which {self.student_name} is expected to return to school",
                    field_type="date",
                    required=False,
                ),
                guava.Field(
                    key="doctor_note_available",
                    description=f"Whether a doctor's note or official documentation will be provided for the absence",
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="parent_aware_of_absence",
                    description=f"Confirmation that {self.parent_name} is aware of and can account for {self.student_name}'s absence",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="additional_message_for_teacher",
                    description="Any message the parent or guardian would like passed along to the teacher or school",
                    field_type="text",
                    required=False,
                ),
            ],
            on_complete=self.save_results,
        )

    def save_results(self):
        results = {
            "timestamp": datetime.now().isoformat(),
            "parent_name": self.parent_name,
            "student_name": self.student_name,
            "absence_date": self.absence_date,
            "periods_missed": self.periods_missed,
            "fields": {
                "absence_reason": self.get_field("absence_reason"),
                "expected_return_date": self.get_field("expected_return_date"),
                "doctor_note_available": self.get_field("doctor_note_available"),
                "parent_aware_of_absence": self.get_field("parent_aware_of_absence"),
                "additional_message_for_teacher": self.get_field("additional_message_for_teacher"),
            },
        }
        print(json.dumps(results, indent=2))
        self.hangup(
            final_instructions=(
                f"Thank {self.parent_name} for taking the time to speak with the school. "
                f"Let them know the absence will be updated in the system and wish {self.student_name} "
                "a speedy recovery or a good rest of the day. End the call warmly."
            )
        )

    def recipient_unavailable(self):
        logging.info(
            "Could not reach parent/guardian %s for attendance check-in (student: %s, date: %s).",
            self.parent_name,
            self.student_name,
            self.absence_date,
        )
        results = {
            "timestamp": datetime.now().isoformat(),
            "parent_name": self.parent_name,
            "student_name": self.student_name,
            "absence_date": self.absence_date,
            "periods_missed": self.periods_missed,
            "outcome": "recipient_unavailable",
        }
        print(json.dumps(results, indent=2))
        self.hangup(
            final_instructions=(
                "The parent or guardian could not be reached. End the call politely."
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Attendance check-in call to parent or guardian for unexcused student absence"
    )
    parser.add_argument("phone", help="Phone number to call (e.g. +15551234567)")
    parser.add_argument("--parent-name", required=True, help="Full name of the parent or guardian")
    parser.add_argument("--student-name", required=True, help="Full name of the student")
    parser.add_argument(
        "--date",
        required=True,
        dest="absence_date",
        help="Date of the absence (e.g. 'February 25, 2026')",
    )
    parser.add_argument(
        "--periods-missed",
        default="the full day",
        help="Which periods or portion of the day were missed (default: 'the full day')",
    )
    args = parser.parse_args()

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=AttendanceCheckinController(
            parent_name=args.parent_name,
            student_name=args.student_name,
            absence_date=args.absence_date,
            periods_missed=args.periods_missed,
        ),
    )
