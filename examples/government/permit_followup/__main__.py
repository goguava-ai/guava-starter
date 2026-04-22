import argparse
import json
import logging
import os
from datetime import datetime, timezone

import guava
from guava import logging_utils

agent = guava.Agent(
    name="Riley",
    organization="City of Springfield - Permitting Office",
    purpose=(
        "contact permit applicants regarding missing information required "
        "to process their application"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(contact_full_name=call.get_variable("applicant_name"))


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    if outcome == "unavailable":
        logging.info(
            "Applicant %s was unavailable for permit follow-up call regarding permit %s.",
            call.get_variable("applicant_name"),
            call.get_variable("permit_number"),
        )
    elif outcome == "available":
        applicant_name = call.get_variable("applicant_name")
        permit_number = call.get_variable("permit_number")
        missing_items = call.get_variable("missing_items")
        call.set_task(
            "followup",
            objective=(
                f"You are calling on behalf of the City of Springfield Permitting Office "
                f"to inform {applicant_name} that their permit or license application "
                f"(permit number {permit_number}) cannot be processed until additional "
                f"information is provided. The missing items are: {missing_items}. "
                "Clearly explain what is needed, ask how they plan to submit the information, "
                "and confirm a commitment date. Be professional, helpful, and neutral in tone."
            ),
            checklist=[
                guava.Say(
                    f"Hello, I'm calling from the City of Springfield Permitting Office "
                    f"regarding permit application number {permit_number}. We have "
                    f"reviewed your application and found that we are unable to proceed "
                    f"without some additional information. The items we still need are: "
                    f"{missing_items}. I have a few quick questions to help us get "
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
        )


@agent.on_task_complete("followup")
def on_done(call: guava.Call) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "applicant_name": call.get_variable("applicant_name"),
        "permit_number": call.get_variable("permit_number"),
        "missing_items": call.get_variable("missing_items"),
        "fields": {
            "missing_info_acknowledged": call.get_field("missing_info_acknowledged"),
            "info_submission_method": call.get_field("info_submission_method"),
            "submission_date_commitment": call.get_field("submission_date_commitment"),
            "cannot_provide_reason": call.get_field("cannot_provide_reason"),
            "additional_questions": call.get_field("additional_questions"),
        },
    }
    print(json.dumps(results, indent=2))
    call.hangup(
        final_instructions=(
            "Thank the applicant for their time. Remind them of the submission method "
            "and date they committed to. Let them know that once all required information "
            "is received, the Permitting Office will continue processing their application. "
            "Provide the office phone number or website if they have further questions, "
            "and end the call courteously."
        )
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

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "applicant_name": args.name,
            "permit_number": args.permit_number,
            "missing_items": args.missing_items,
        },
    )
