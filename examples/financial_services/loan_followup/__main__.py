import guava
import os
import logging
from guava import logging_utils
import json
import argparse
from datetime import datetime, timezone



agent = guava.Agent(
    name="Taylor",
    organization="First National Bank",
    purpose=(
        "to follow up on a pending loan application and collect "
        "outstanding documentation required to move the application forward"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(contact_full_name=call.get_variable("contact_name"))


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    if outcome == "unavailable":
        call.hangup(
            final_instructions=(
                f"You were unable to reach {call.get_variable('contact_name')}. Leave a brief, professional "
                f"voicemail introducing yourself as Taylor from First National Bank, mentioning "
                f"that you are calling about their {call.get_variable('loan_type')} application and that there are "
                f"outstanding documents needed to proceed. Ask them to call back at their earliest "
                f"convenience and provide the bank's main customer service line."
            )
        )
    elif outcome == "available":
        call.set_task(
            "followup",
            objective=(
                f"You are following up with {call.get_variable('contact_name')} regarding their {call.get_variable('loan_type')} "
                f"application at First National Bank. The application is currently on hold because "
                f"the following documentation is missing: {call.get_variable('missing_docs')}. Your goal is to "
                f"inform the applicant of the missing items, answer any eligibility questions they "
                f"may have, confirm how they will submit the documents, and schedule a submission "
                f"date so the application can move forward."
            ),
            checklist=[
                guava.Say(
                    f"Hello {call.get_variable('contact_name')}, I'm calling from First National Bank regarding "
                    f"your {call.get_variable('loan_type')} application. I want to let you know that your "
                    f"application is progressing, but we do need a couple of additional documents "
                    f"before we can finalize a decision."
                ),
                guava.Say(
                    f"The outstanding item we need from you is: {call.get_variable('missing_docs')}. "
                    f"I am happy to answer any questions you have about why we need this or what "
                    f"qualifies as acceptable documentation."
                ),
                guava.Field(
                    key="missing_documents_acknowledged",
                    description=(
                        f"Confirm that the applicant understands which documents are missing "
                        f"({call.get_variable('missing_docs')}) and acknowledges they need to submit them. "
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
        )


@agent.on_task_complete("followup")
def on_done(call: guava.Call) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "contact_name": call.get_variable("contact_name"),
        "loan_type": call.get_variable("loan_type"),
        "missing_docs": call.get_variable("missing_docs"),
        "missing_documents_acknowledged": call.get_field("missing_documents_acknowledged"),
        "document_submission_method": call.get_field("document_submission_method"),
        "preferred_submission_date": call.get_field("preferred_submission_date"),
        "additional_questions": call.get_field("additional_questions"),
    }
    print(json.dumps(results, indent=2))
    call.hangup(
        final_instructions=(
            f"Thank {call.get_variable('contact_name')} for their time and for confirming the document "
            f"submission details. Let them know that once we receive the {call.get_variable('missing_docs')}, "
            f"a loan officer will review the application and reach out within 2 to 3 business "
            f"days with a decision. Wish them a great day and close the call warmly."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
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

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "contact_name": args.name,
            "loan_type": args.loan_type,
            "missing_docs": args.missing_docs,
        },
    )
