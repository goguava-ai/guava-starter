import guava
import os
import logging
import json
import requests
from datetime import datetime

logging.basicConfig(level=logging.INFO)

FHIR_BASE_URL = os.environ["MEDITECH_FHIR_BASE_URL"]


def get_headers() -> dict:
    return {
        "Authorization": f"Bearer {os.environ['MEDITECH_ACCESS_TOKEN']}",
        "Content-Type": "application/json",
        "Accept": "application/fhir+json",
    }


class MedicationInquiryController(guava.CallController):
    def __init__(self):
        super().__init__()
        self.patient_fhir_id = None
        self.active_medications = []

        self.set_persona(
            organization_name="Valley General Hospital",
            agent_name="Alex",
            agent_purpose=(
                "to help patients review the medications currently on file for them at "
                "Valley General Hospital and address questions, refill needs, or discrepancies"
            ),
        )

        self.set_task(
            objective=(
                "A patient has called Valley General Hospital to inquire about their current "
                "medications on file. Greet them, verify their identity, and prepare to look "
                "up their medication record."
            ),
            checklist=[
                guava.Say(
                    "Thank you for calling Valley General Hospital. My name is Alex. "
                    "I can help you review the medications we currently have on file for you. "
                    "First I'll need to verify your identity."
                ),
                guava.Field(
                    key="first_name",
                    description="Ask the caller for their first name.",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="last_name",
                    description="Ask the caller for their last name.",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="date_of_birth",
                    description=(
                        "Ask for the patient's date of birth to verify their identity. "
                        "Capture in YYYY-MM-DD format (e.g. 1972-06-20)."
                    ),
                    field_type="text",
                    required=True,
                ),
            ],
            on_complete=self.lookup_medications,
        )

        self.accept_call()

    def lookup_medications(self):
        first_name = self.get_field("first_name")
        last_name = self.get_field("last_name")
        dob = self.get_field("date_of_birth")

        logging.info(
            "Looking up medications for %s %s (DOB: %s).", first_name, last_name, dob
        )

        try:
            # Step 1: Look up the patient by last name + DOB to get their FHIR resource ID.
            patient_resp = requests.get(
                f"{FHIR_BASE_URL}/Patient",
                headers=get_headers(),
                params={"family": last_name, "birthdate": dob},
                timeout=10,
            )
            patient_resp.raise_for_status()
            patient_entries = patient_resp.json().get("entry", [])

            if not patient_entries:
                logging.warning(
                    "No matching patient found in Meditech for %s %s (DOB: %s).",
                    first_name, last_name, dob,
                )
                self.hangup(
                    final_instructions=(
                        f"Apologize to the caller and let them know we were not able to find a "
                        "patient record matching the information they provided in Valley General "
                        "Hospital's system. Ask them to double-check the spelling of their last "
                        "name and date of birth, and encourage them to call back or visit the "
                        "hospital's patient services desk for further assistance. Thank them for calling."
                    )
                )
                return

            self.patient_fhir_id = patient_entries[0]["resource"]["id"]
            logging.info("Found patient in Meditech: %s", self.patient_fhir_id)

            # Step 2: Fetch active MedicationStatements for the patient.
            # Each resource's medicationCodeableConcept.text field contains the human-readable
            # medication name and dosage as recorded by the clinical team in Meditech Expanse.
            med_resp = requests.get(
                f"{FHIR_BASE_URL}/MedicationStatement",
                headers=get_headers(),
                params={
                    "subject": f"Patient/{self.patient_fhir_id}",
                    "status": "active",
                },
                timeout=10,
            )
            med_resp.raise_for_status()
            med_entries = med_resp.json().get("entry", [])

            for entry in med_entries:
                resource = entry.get("resource", {})
                med_text = (
                    resource.get("medicationCodeableConcept", {}).get("text")
                    or next(
                        (
                            c.get("display")
                            for c in resource.get("medicationCodeableConcept", {}).get("coding", [])
                            if c.get("display")
                        ),
                        None,
                    )
                )
                dosage_list = resource.get("dosage", [])
                dosage_text = (
                    dosage_list[0].get("text") if dosage_list else None
                )
                if med_text:
                    label = med_text
                    if dosage_text:
                        label = f"{med_text} — {dosage_text}"
                    self.active_medications.append(label)

            logging.info(
                "Found %d active medication(s) for patient %s.",
                len(self.active_medications),
                self.patient_fhir_id,
            )
        except Exception as e:
            logging.error("Failed to look up medications in Meditech: %s", e)

        self._present_medications(first_name)

    def _present_medications(self, first_name: str):
        if self.active_medications:
            med_count = len(self.active_medications)
            med_list_spoken = "; ".join(self.active_medications)
            medications_intro = (
                f"We currently have {med_count} active medication(s) on file for you: "
                f"{med_list_spoken}."
            )
        else:
            medications_intro = (
                "We don't currently have any active medications on file for you in our system."
            )

        self.set_task(
            objective=(
                f"Read back the active medications on file for {first_name} and ask "
                "if they have any questions, need a refill, are just checking, or if "
                "something looks incorrect."
            ),
            checklist=[
                guava.Say(medications_intro),
                guava.Field(
                    key="inquiry_reason",
                    description=(
                        "After reading the medication list, ask the patient what they would "
                        "like to do or if there is something specific you can help them with. "
                        "Options are: have questions, need refill, just checking, or wrong medication listed. "
                        "Capture their choice exactly."
                    ),
                    field_type="multiple_choice",
                    choices=[
                        "have questions",
                        "need refill",
                        "just checking",
                        "wrong medication listed",
                    ],
                    required=True,
                ),
            ],
            on_complete=self.handle_inquiry_reason,
        )

    def handle_inquiry_reason(self):
        first_name = self.get_field("first_name")
        last_name = self.get_field("last_name")
        inquiry_reason = self.get_field("inquiry_reason")

        results = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "agent": "Alex",
            "organization": "Valley General Hospital",
            "use_case": "medication_inquiry",
            "patient_fhir_id": self.patient_fhir_id,
            "active_medications": self.active_medications,
            "fields": {
                "first_name": first_name,
                "last_name": last_name,
                "date_of_birth": self.get_field("date_of_birth"),
                "inquiry_reason": inquiry_reason,
            },
        }
        print(json.dumps(results, indent=2))
        logging.info("Medication inquiry complete. Reason: %s", inquiry_reason)

        reason = (inquiry_reason or "").strip().lower()

        if reason == "have questions":
            self.hangup(
                final_instructions=(
                    f"Acknowledge that {first_name} has questions about their medications. "
                    "Let them know that a member of the clinical pharmacy team at Valley General "
                    "Hospital will call them back within one business day to address their questions. "
                    "Remind them that for urgent medication concerns they can also speak with a "
                    "pharmacist at their local pharmacy. Thank them for calling."
                )
            )

        elif reason == "need refill":
            self.hangup(
                final_instructions=(
                    f"Let {first_name} know that their refill request has been noted and will be "
                    "forwarded to their prescribing provider at Valley General Hospital for review. "
                    "Let them know refill requests are typically processed within 1–2 business days "
                    "and they will receive notification when the prescription is ready at their pharmacy. "
                    "Remind them to contact their pharmacy directly if they have an urgent need. "
                    "Thank them for calling."
                )
            )

        elif reason == "wrong medication listed":
            self.hangup(
                final_instructions=(
                    f"Acknowledge {first_name}'s concern that a medication on file may be incorrect. "
                    "Let them know this will be escalated to their care team at Valley General Hospital "
                    "for review and correction. Ask them not to stop or change any medications on their "
                    "own without first speaking with their provider. A nurse or pharmacist will contact "
                    "them within one business day to clarify the record. Thank them for bringing this "
                    "to our attention."
                )
            )

        else:
            # "just checking" or any unexpected value — simple, friendly close.
            self.hangup(
                final_instructions=(
                    f"Thank {first_name} for calling Valley General Hospital to review their "
                    "medication record. Remind them they can call back any time with questions "
                    "or if anything changes. Wish them a great day."
                )
            )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=MedicationInquiryController,
    )
