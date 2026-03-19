import guava
import os
import logging
import json
import argparse
from datetime import datetime

logging.basicConfig(level=logging.INFO)


class InsurancePreauthController(guava.CallController):
    def __init__(self, patient_name: str, procedure_name: str):
        super().__init__()
        self.patient_name = patient_name
        self.procedure_name = procedure_name

        self.set_persona(
            organization_name="Riverside Medical Center - Billing Department",
            agent_name="Casey",
            agent_purpose=(
                "to contact insurance carriers on behalf of Riverside Medical Center to obtain "
                "pre-authorization details for scheduled patient procedures"
            ),
        )

        self.set_task(
            objective=(
                f"Call the insurance carrier to obtain pre-authorization for the procedure "
                f"'{self.procedure_name}' for patient {self.patient_name}. Identify the "
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
            on_complete=self.save_results,
        )

    def save_results(self):
        results = {
            "timestamp": datetime.now().isoformat(),
            "patient_name": self.patient_name,
            "procedure_name": self.procedure_name,
            "auth_representative_name": self.get_field("auth_representative_name"),
            "auth_number": self.get_field("auth_number"),
            "covered": self.get_field("covered"),
            "coverage_limitations": self.get_field("coverage_limitations"),
            "effective_date": self.get_field("effective_date"),
        }
        print(json.dumps(results, indent=2))
        logging.info("Insurance pre-authorization results saved.")

        decision = self.get_field("covered")
        if decision and str(decision).strip().lower() == "approved":
            self.hangup(
                final_instructions=(
                    "Thank the representative for their time and for processing the authorization. "
                    "Confirm that Riverside Medical Center has all the information needed and that the "
                    "authorization number has been recorded. Wish them a good day."
                )
            )
        elif decision and str(decision).strip().lower() == "denied":
            self.hangup(
                final_instructions=(
                    "Thank the representative for the information. Let them know that Riverside Medical "
                    "Center's billing team will review the denial and may follow up regarding an appeal. "
                    "Ask if there is a direct line or reference number for the appeals department before "
                    "ending the call. Wish them a good day."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    "Thank the representative for their time. Let them know Riverside Medical Center will "
                    "follow up on the pending authorization status. Ask for an expected turnaround time and "
                    "a callback number or reference to check status. Wish them a good day."
                )
            )

    def recipient_unavailable(self):
        self.hangup(
            final_instructions=(
                "We were unable to reach an authorization representative. Leave a brief, professional "
                "voicemail on behalf of Riverside Medical Center Billing Department requesting a callback "
                f"to process a pre-authorization for patient {self.patient_name} for the procedure "
                f"'{self.procedure_name}'. Provide a callback number if available."
            )
        )


if __name__ == "__main__":
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

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=InsurancePreauthController(
            patient_name=args.patient,
            procedure_name=args.procedure,
        ),
    )
