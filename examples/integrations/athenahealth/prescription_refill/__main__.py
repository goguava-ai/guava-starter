import guava
import os
import logging
import argparse
import requests

logging.basicConfig(level=logging.INFO)

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


def request_refill(patient_id: str, medication: str, pharmacy: str, headers: dict) -> bool:
    """Creates a medication refill request in the patient chart."""
    resp = requests.post(
        f"{BASE_URL}/patients/{patient_id}/medications",
        headers={**headers, "Content-Type": "application/x-www-form-urlencoded"},
        data={
            "medicationname": medication,
            "refillrequestreason": f"Patient requested refill via phone. Preferred pharmacy: {pharmacy}",
            "issafetorenew": "true",
        },
        timeout=10,
    )
    return resp.ok


class PrescriptionRefillController(guava.CallController):
    def __init__(self, patient_name: str, patient_id: str, medication: str):
        super().__init__()
        self.patient_name = patient_name
        self.patient_id = patient_id
        self.medication = medication
        self.headers = {}

        try:
            token = get_access_token()
            self.headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/x-www-form-urlencoded",
            }
        except Exception as e:
            logging.error("Failed to get Athenahealth token: %s", e)

        self.set_persona(
            organization_name="Maple Medical Group",
            agent_name="Avery",
            agent_purpose=(
                "to help patients request prescription refills quickly and route them to the care team"
            ),
        )

        self.set_task(
            objective=(
                f"Call {patient_name} about a refill for {medication}. Confirm they still need "
                "the refill, check for any new symptoms or concerns, and collect their preferred pharmacy."
            ),
            checklist=[
                guava.Say(
                    f"Hi {patient_name}, this is Avery calling from Maple Medical Group "
                    f"regarding a refill request for {medication}."
                ),
                guava.Field(
                    key="still_needs_refill",
                    field_type="multiple_choice",
                    description="Confirm the patient still needs the refill.",
                    choices=["yes", "no"],
                    required=True,
                ),
                guava.Field(
                    key="new_symptoms",
                    field_type="multiple_choice",
                    description=(
                        "Ask if they've experienced any new or worsening symptoms since "
                        "they last took this medication."
                    ),
                    choices=["yes", "no"],
                    required=True,
                ),
                guava.Field(
                    key="symptom_details",
                    field_type="text",
                    description=(
                        "If they said yes to new symptoms, ask them to briefly describe what they've noticed. "
                        "Skip this if they said no."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="pharmacy",
                    field_type="text",
                    description=(
                        "Ask which pharmacy they'd like the prescription sent to. "
                        "Capture name and location (e.g., 'CVS on Main Street')."
                    ),
                    required=True,
                ),
            ],
            on_complete=self.submit_refill,
        )

        self.reach_person(
            contact_full_name=self.patient_name,
            on_success=lambda: None,
            on_failure=self.recipient_unavailable,
        )

    def submit_refill(self):
        still_needs = self.get_field("still_needs_refill") or ""
        pharmacy = self.get_field("pharmacy") or "patient's preferred pharmacy"
        symptoms = self.get_field("symptom_details") or ""

        if "no" in still_needs:
            logging.info("Patient %s no longer needs refill for %s.", self.patient_id, self.medication)
            self.hangup(
                final_instructions=(
                    f"Acknowledge that {self.patient_name} no longer needs the refill. "
                    "Let them know no action will be taken and that they can call back anytime. "
                    "Wish them a great day."
                )
            )
            return

        logging.info(
            "Submitting refill for patient %s: %s → %s",
            self.patient_id, self.medication, pharmacy,
        )

        success = False
        try:
            success = request_refill(self.patient_id, self.medication, pharmacy, self.headers)
            logging.info("Refill request submitted: %s", success)
        except Exception as e:
            logging.error("Failed to submit refill for patient %s: %s", self.patient_id, e)

        symptom_note = (
            f" Note: patient reported new symptoms — '{symptoms}'. The care team should review before approving."
            if symptoms else ""
        )

        if success:
            self.hangup(
                final_instructions=(
                    f"Let {self.patient_name} know their refill request for {self.medication} "
                    f"has been submitted to the care team and will be sent to {pharmacy}. "
                    f"Let them know to expect it within 1–2 business days.{symptom_note} "
                    "Thank them for calling and wish them a great day."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Apologize to {self.patient_name} — let them know there was an issue submitting "
                    "the refill request and that a team member will follow up by end of day. "
                    "Thank them for their patience."
                )
            )

    def recipient_unavailable(self):
        logging.info("Unable to reach %s for prescription refill.", self.patient_name)
        self.hangup(
            final_instructions=(
                f"Leave a brief voicemail for {self.patient_name} from Maple Medical Group. "
                f"Let them know you're calling regarding a refill for {self.medication} "
                "and ask them to call back to confirm their pharmacy preference. "
                "Keep it concise."
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Outbound prescription refill confirmation via Athenahealth."
    )
    parser.add_argument("phone", help="Patient phone number (E.164, e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Patient's full name")
    parser.add_argument("--patient-id", required=True, help="Athenahealth patient ID")
    parser.add_argument("--medication", required=True, help="Medication name and dosage (e.g. 'Lisinopril 10mg')")
    args = parser.parse_args()

    logging.info(
        "Initiating prescription refill call to %s (%s) for %s",
        args.name, args.phone, args.medication,
    )

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=PrescriptionRefillController(
            patient_name=args.name,
            patient_id=args.patient_id,
            medication=args.medication,
        ),
    )
