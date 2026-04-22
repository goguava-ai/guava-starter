import argparse
import json
import logging
import os
from datetime import datetime

import guava
from guava import logging_utils

agent = guava.Agent(
    name="Casey",
    organization="Riverside Medical Center - Billing Department",
    purpose=(
        "to contact insurance carriers on behalf of Riverside Medical Center to obtain "
        "pre-authorization details for scheduled patient procedures"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    procedure_name = call.get_variable("procedure_name")
    call.set_task(
        "verification",
        objective=(
            f"Call the insurance carrier to obtain pre-authorization for the procedure "
            f"'{procedure_name}' for patient {patient_name}. Identify the "
            "authorization representative, record the authorization number and decision, "
            "note any coverage limitations, and confirm the effective date of the authorization. "
            "Be professional, clear, and thorough in collecting all required billing information."
        ),
        checklist=[
            guava.Say(
                "Hello, this is Casey calling from the Billing Department at Riverside Medical Center. "
                "I'm reaching out to request a pre-authorization for an upcoming procedure for one of "
                "our patients. May I please speak with someone who can assist with pre-authorization requests?"
            ),
            guava.Field(
                key="auth_representative_name",
                description=(
                    "Ask for and capture the full name of the insurance representative handling "
                    "this pre-authorization request."
                ),
                field_type="text",
                required=True,
            ),
            "Provide the patient name, date of birth if requested, and the procedure name to the representative. "
            f"Patient: {patient_name}. Procedure: {procedure_name}.",
            guava.Field(
                key="auth_number",
                description=(
                    "Ask the representative for the pre-authorization reference or confirmation number "
                    "assigned to this request. Capture the full alphanumeric code exactly as provided."
                ),
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="covered",
                description=(
                    "Ask the representative for the authorization decision on the procedure. "
                    "Capture one of: 'approved', 'denied', or 'pending'."
                ),
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="coverage_limitations",
                description=(
                    "Ask if there are any coverage limitations, restrictions, or conditions attached "
                    "to this authorization (e.g., facility restrictions, quantity limits, required "
                    "referrals). Capture any details provided. Skip if none."
                ),
                field_type="text",
                required=False,
            ),
            guava.Field(
                key="effective_date",
                description=(
                    "Ask for the effective date of the authorization — the date from which the "
                    "pre-authorization is valid for the procedure to be performed."
                ),
                field_type="date",
                required=True,
            ),
        ],
    )


@agent.on_task_complete("verification")
def on_done(call: guava.Call) -> None:
    results = {
        "timestamp": datetime.now().isoformat(),
        "patient_name": call.get_variable("patient_name"),
        "procedure_name": call.get_variable("procedure_name"),
        "auth_representative_name": call.get_field("auth_representative_name"),
        "auth_number": call.get_field("auth_number"),
        "covered": call.get_field("covered"),
        "coverage_limitations": call.get_field("coverage_limitations"),
        "effective_date": call.get_field("effective_date"),
    }
    print(json.dumps(results, indent=2))
    logging.info("Insurance pre-authorization results saved.")

    decision = call.get_field("covered")
    if decision and str(decision).strip().lower() == "approved":
        call.hangup(
            final_instructions=(
                "Thank the representative for their time and for processing the authorization. "
                "Confirm that Riverside Medical Center has all the information needed and that the "
                "authorization number has been recorded. Wish them a good day."
            )
        )
    elif decision and str(decision).strip().lower() == "denied":
        call.hangup(
            final_instructions=(
                "Thank the representative for the information. Let them know that Riverside Medical "
                "Center's billing team will review the denial and may follow up regarding an appeal. "
                "Ask if there is a direct line or reference number for the appeals department before "
                "ending the call. Wish them a good day."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                "Thank the representative for their time. Let them know Riverside Medical Center will "
                "follow up on the pending authorization status. Ask for an expected turnaround time and "
                "a callback number or reference to check status. Wish them a good day."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound insurance pre-authorization call for Riverside Medical Center."
    )
    parser.add_argument("phone", help="Insurance carrier phone number to call")
    parser.add_argument("--patient", required=True, help="Full name of the patient")
    parser.add_argument("--procedure", required=True, help="Name of the procedure requiring pre-authorization")
    args = parser.parse_args()

    logging.info(
        "Initiating insurance pre-authorization call to %s for patient: %s, procedure: %s",
        args.phone,
        args.patient,
        args.procedure,
    )

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "patient_name": args.patient,
            "procedure_name": args.procedure,
        },
    )
