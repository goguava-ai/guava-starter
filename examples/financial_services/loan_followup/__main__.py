import guava
import os
import logging
import json
import argparse
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)


class LoanFollowupController(guava.CallController):
    def __init__(self, contact_name: str, loan_type: str, missing_docs: str):
        super().__init__()
        self.contact_name = contact_name
        self.loan_type = loan_type
        self.missing_docs = missing_docs

        self.set_persona(
            organization_name="First National Bank",
            agent_name="Taylor",
            agent_purpose=(
                f"to follow up on a pending {self.loan_type} application and collect "
                f"outstanding documentation required to move the application forward"
            ),
        )

        self.reach_person(
            contact_full_name=self.contact_name,
            on_success=self.begin_loan_followup,
            on_failure=self.recipient_unavailable,
        )

    def begin_loan_followup(self):
        self.set_task(
            objective=(
                f"You are following up with {self.contact_name} regarding their {self.loan_type} "
                f"application at First National Bank. The application is currently on hold because "
                f"the following documentation is missing: {self.missing_docs}. Your goal is to "
                f"inform the applicant of the missing items, answer any eligibility questions they "
                f"may have, confirm how they will submit the documents, and schedule a submission "
                f"date so the application can move forward."
            ),
            checklist=[
                guava.Say(
                    f"Hello {self.contact_name}, I'm calling from First National Bank regarding "
                    f"your {self.loan_type} application. I want to let you know that your "
                    f"application is progressing, but we do need a couple of additional documents "
                    f"before we can finalize a decision."
                ),
                guava.Say(
                    f"The outstanding item we need from you is: {self.missing_docs}. "
                    f"I am happy to answer any questions you have about why we need this or what "
                    f"qualifies as acceptable documentation."
                ),
                guava.Field(
                    key="missing_documents_acknowledged",
                    description=(
                        f"Confirm that the applicant understands which documents are missing "
                        f"({self.missing_docs}) and acknowledges they need to submit them. "
                        f"Record a brief summary of their acknowledgment or any clarifications provided."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Say(
                    "We accept documents via email, fax, or in person at any branch location. "
                    "Which method works best for you?"
                ),
                guava.Field(
                    key="document_submission_method",
                    description=(
                        "The method the applicant has chosen to submit their documents. "
                        "Expected values: 'email', 'fax', or 'branch'."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="preferred_submission_date",
                    description=(
                        "The date by which the applicant expects to submit the required documents. "
                        "Confirm a specific date with the applicant."
                    ),
                    field_type="date",
                    required=True,
                ),
                guava.Field(
                    key="additional_questions",
                    description=(
                        "Any additional questions or concerns the applicant raised during the call "
                        "about their loan application, eligibility, interest rates, or timeline. "
                        "Leave blank if none."
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
            "contact_name": self.contact_name,
            "loan_type": self.loan_type,
            "missing_docs": self.missing_docs,
            "missing_documents_acknowledged": self.get_field("missing_documents_acknowledged"),
            "document_submission_method": self.get_field("document_submission_method"),
            "preferred_submission_date": self.get_field("preferred_submission_date"),
            "additional_questions": self.get_field("additional_questions"),
        }
        print(json.dumps(results, indent=2))
        self.hangup(
            final_instructions=(
                f"Thank {self.contact_name} for their time and for confirming the document "
                f"submission details. Let them know that once we receive the {self.missing_docs}, "
                f"a loan officer will review the application and reach out within 2 to 3 business "
                f"days with a decision. Wish them a great day and close the call warmly."
            )
        )

    def recipient_unavailable(self):
        self.hangup(
            final_instructions=(
                f"You were unable to reach {self.contact_name}. Leave a brief, professional "
                f"voicemail introducing yourself as Taylor from First National Bank, mentioning "
                f"that you are calling about their {self.loan_type} application and that there are "
                f"outstanding documents needed to proceed. Ask them to call back at their earliest "
                f"convenience and provide the bank's main customer service line."
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Loan follow-up call to collect missing documentation."
    )
    parser.add_argument("phone", help="The phone number to call (E.164 format, e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Full name of the loan applicant")
    parser.add_argument(
        "--loan-type",
        default="personal loan",
        help="Type of loan (default: 'personal loan')",
    )
    parser.add_argument(
        "--missing-docs",
        default="proof of income",
        help="Description of missing documents (default: 'proof of income')",
    )
    args = parser.parse_args()

    controller = LoanFollowupController(
        contact_name=args.name,
        loan_type=args.loan_type,
        missing_docs=args.missing_docs,
    )

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=controller,
    )
