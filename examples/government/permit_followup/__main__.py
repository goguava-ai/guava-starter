import guava
import os
import logging
from guava import logging_utils
import json
import argparse
from datetime import datetime, timezone



class PermitFollowupController(guava.CallController):
    def __init__(self, applicant_name: str, permit_number: str, missing_items: str):
        super().__init__()
        self.applicant_name = applicant_name
        self.permit_number = permit_number
        self.missing_items = missing_items
        self.set_persona(
            organization_name="City of Springfield - Permitting Office",
            agent_name="Riley",
            agent_purpose=(
                "contact permit applicants regarding missing information required "
                "to process their application"
            ),
        )
        self.reach_person(
            contact_full_name=self.applicant_name,
            on_success=self.begin_followup,
            on_failure=self.recipient_unavailable,
        )

    def begin_followup(self):
        self.set_task(
            objective=(
                f"You are calling on behalf of the City of Springfield Permitting Office "
                f"to inform {self.applicant_name} that their permit or license application "
                f"(permit number {self.permit_number}) cannot be processed until additional "
                f"information is provided. The missing items are: {self.missing_items}. "
                "Clearly explain what is needed, ask how they plan to submit the information, "
                "and confirm a commitment date. Be professional, helpful, and neutral in tone."
            ),
            checklist=[
                guava.Say(
                    f"Hello, I'm calling from the City of Springfield Permitting Office "
                    f"regarding permit application number {self.permit_number}. We have "
                    f"reviewed your application and found that we are unable to proceed "
                    f"without some additional information. The items we still need are: "
                    f"{self.missing_items}. I have a few quick questions to help us get "
                    "your application moving forward."
                ),
                guava.Field(
                    key="missing_info_acknowledged",
                    description=(
                        "Confirm that the applicant understands which items are missing "
                        "and ask them to acknowledge receipt of this information."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="info_submission_method",
                    description=(
                        "Ask how the applicant plans to submit the missing information: "
                        "by email, by mail, in person, or through the online portal."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="submission_date_commitment",
                    description=(
                        "Ask the applicant for the date by which they expect to submit "
                        "the missing information."
                    ),
                    field_type="date",
                    required=True,
                ),
                guava.Field(
                    key="cannot_provide_reason",
                    description=(
                        "If the applicant indicates they are unable to provide any of the "
                        "missing items, ask them to explain why."
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="additional_questions",
                    description=(
                        "Ask if the applicant has any questions about the missing requirements "
                        "or the application process."
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
            "applicant_name": self.applicant_name,
            "permit_number": self.permit_number,
            "missing_items": self.missing_items,
            "fields": {
                "missing_info_acknowledged": self.get_field("missing_info_acknowledged"),
                "info_submission_method": self.get_field("info_submission_method"),
                "submission_date_commitment": self.get_field("submission_date_commitment"),
                "cannot_provide_reason": self.get_field("cannot_provide_reason"),
                "additional_questions": self.get_field("additional_questions"),
            },
        }
        print(json.dumps(results, indent=2))
        self.hangup(
            final_instructions=(
                "Thank the applicant for their time. Remind them of the submission method "
                "and date they committed to. Let them know that once all required information "
                "is received, the Permitting Office will continue processing their application. "
                "Provide the office phone number or website if they have further questions, "
                "and end the call courteously."
            )
        )

    def recipient_unavailable(self):
        logging.info(
            "Applicant %s was unavailable for permit follow-up call regarding permit %s.",
            self.applicant_name,
            self.permit_number,
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound permit follow-up call for City of Springfield Permitting Office."
    )
    parser.add_argument("phone", help="Applicant phone number to call (E.164 format).")
    parser.add_argument("--name", required=True, help="Full name of the permit applicant.")
    parser.add_argument("--permit-number", required=True, help="Permit or license application number.")
    parser.add_argument(
        "--missing-items",
        required=True,
        help="Description of the information or documents still required to process the application.",
    )
    args = parser.parse_args()

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=PermitFollowupController(
            applicant_name=args.name,
            permit_number=args.permit_number,
            missing_items=args.missing_items,
        ),
    )
