import guava
import os
import logging
from guava import logging_utils
import argparse
import requests


PRACTICE_ID = os.environ["ATHENA_PRACTICE_ID"]
BASE_URL = f"https://api.platform.athenahealth.com/v1/{PRACTICE_ID}"


def get_access_token() -> str:
    resp = requests.post(
        "https://api.platform.athenahealth.com/oauth2/v1/token",
        data={"grant_type": "client_credentials"},
        auth=(os.environ["ATHENA_CLIENT_ID"], os.environ["ATHENA_CLIENT_SECRET"]),
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def get_patient_insurances(patient_id: str, headers: dict) -> list:
    resp = requests.get(
        f"{BASE_URL}/patients/{patient_id}/insurances",
        headers=headers,
        timeout=10,
    )
    if not resp.ok:
        return []
    return resp.json().get("insurances", [])


def post_insurance(patient_id: str, payload: dict, headers: dict) -> bool:
    resp = requests.post(
        f"{BASE_URL}/patients/{patient_id}/insurances",
        headers={**headers, "Content-Type": "application/x-www-form-urlencoded"},
        data=payload,
        timeout=10,
    )
    return resp.ok


class InsuranceVerificationController(guava.CallController):
    def __init__(self, patient_name: str, patient_id: str):
        super().__init__()
        self.patient_name = patient_name
        self.patient_id = patient_id
        self.headers = {}
        self.existing_insurance = None

        try:
            token = get_access_token()
            self.headers = {"Authorization": f"Bearer {token}"}
            insurances = get_patient_insurances(patient_id, self.headers)
            if insurances:
                self.existing_insurance = insurances[0]
                logging.info(
                    "Insurance on file for patient %s: %s",
                    patient_id,
                    self.existing_insurance.get("insuranceplanname", "unknown"),
                )
        except Exception as e:
            logging.error("Failed to load insurance for patient %s: %s", patient_id, e)

        self.set_persona(
            organization_name="Maple Medical Group",
            agent_name="Avery",
            agent_purpose=(
                "to verify and update patient insurance information before upcoming visits"
            ),
        )

        if self.existing_insurance:
            ins_name = self.existing_insurance.get("insuranceplanname", "your current plan")
            ins_id = self.existing_insurance.get("insuranceidnumber", "")
            pre_intro = (
                f"Insurance currently on file: {ins_name}"
                + (f" (ID: {ins_id})" if ins_id else "")
                + ". Verify this is still accurate."
            )
        else:
            pre_intro = "No insurance on file. Collect new insurance details."

        self.set_task(
            objective=(
                f"Verify insurance information for {patient_name} before their upcoming visit. "
                + pre_intro
            ),
            checklist=[
                guava.Say(
                    f"Hi {patient_name}, this is Avery calling from Maple Medical Group. "
                    "I'm calling to quickly verify your insurance information before your upcoming visit."
                ),
                guava.Field(
                    key="insurance_current",
                    field_type="multiple_choice",
                    description=(
                        f"Ask if their insurance is still {'the same — ' + self.existing_insurance.get('insuranceplanname', '') if self.existing_insurance else 'the same as before'}. "
                        "Capture yes or no."
                    ),
                    choices=["yes", "no"],
                    required=True,
                ),
                guava.Field(
                    key="insurance_provider",
                    field_type="text",
                    description=(
                        "If their insurance changed (or there's none on file), ask for the name of "
                        "their current insurance provider. Skip if they said yes to current insurance."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="member_id",
                    field_type="text",
                    description=(
                        "If their insurance changed, ask for their member ID or policy number. "
                        "Skip if unchanged."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="group_number",
                    field_type="text",
                    description=(
                        "If their insurance changed, ask for the group number if they have one. "
                        "Skip if unchanged."
                    ),
                    required=False,
                ),
            ],
            on_complete=self.update_insurance,
        )

        self.reach_person(
            contact_full_name=self.patient_name,
            on_success=lambda: None,
            on_failure=self.recipient_unavailable,
        )

    def update_insurance(self):
        insurance_current = self.get_field("insurance_current") or ""
        provider = self.get_field("insurance_provider") or ""
        member_id = self.get_field("member_id") or ""
        group_number = self.get_field("group_number") or ""

        if "yes" in insurance_current:
            logging.info("Insurance verified as current for patient %s.", self.patient_id)
            self.hangup(
                final_instructions=(
                    f"Thank {self.patient_name} for confirming their insurance is up to date. "
                    "Let them know they're all set for their upcoming visit. "
                    "Remind them to bring their insurance card just in case. "
                    "Wish them a great day."
                )
            )
            return

        if provider:
            logging.info(
                "Updating insurance for patient %s: %s / %s / %s",
                self.patient_id, provider, member_id, group_number,
            )
            payload = {"insuranceplanname": provider}
            if member_id:
                payload["insuranceidnumber"] = member_id
            if group_number:
                payload["insurancegroupnumber"] = group_number

            success = False
            try:
                success = post_insurance(self.patient_id, payload, self.headers)
                logging.info("Insurance updated: %s", success)
            except Exception as e:
                logging.error("Failed to update insurance for patient %s: %s", self.patient_id, e)

            if success:
                self.hangup(
                    final_instructions=(
                        f"Let {self.patient_name} know their insurance information has been updated "
                        f"to {provider}. Ask them to bring their insurance card to the visit. "
                        "Thank them and wish them a great day."
                    )
                )
            else:
                self.hangup(
                    final_instructions=(
                        f"Apologize to {self.patient_name} — let them know we weren't able to update "
                        "their insurance information automatically. Ask them to bring their insurance "
                        "card to the visit and our front desk will assist them. "
                        "Thank them for their patience."
                    )
                )
        else:
            self.hangup(
                final_instructions=(
                    f"Let {self.patient_name} know we'll need their updated insurance information "
                    "at check-in. Ask them to bring their insurance card to the visit. "
                    "Thank them for calling and wish them a great day."
                )
            )

    def recipient_unavailable(self):
        logging.info("Unable to reach %s for insurance verification.", self.patient_name)
        self.hangup(
            final_instructions=(
                f"Leave a brief voicemail for {self.patient_name} from Maple Medical Group. "
                "Let them know you're calling to verify insurance before their upcoming visit "
                "and ask them to call back or bring their insurance card to check-in. "
                "Keep it concise."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound insurance verification call via Athenahealth."
    )
    parser.add_argument("phone", help="Patient phone number (E.164, e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Patient's full name")
    parser.add_argument("--patient-id", required=True, help="Athenahealth patient ID")
    args = parser.parse_args()

    logging.info(
        "Initiating insurance verification call to %s (%s)", args.name, args.phone
    )

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=InsuranceVerificationController(
            patient_name=args.name,
            patient_id=args.patient_id,
        ),
    )
