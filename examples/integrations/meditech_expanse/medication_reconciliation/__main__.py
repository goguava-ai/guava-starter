import guava
import os
import logging
import argparse
import requests
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)

FHIR_BASE_URL = os.environ["MEDITECH_FHIR_BASE_URL"]


def get_headers() -> dict:
    return {
        "Authorization": f"Bearer {os.environ['MEDITECH_ACCESS_TOKEN']}",
        "Content-Type": "application/json",
        "Accept": "application/fhir+json",
    }


def fetch_medication_requests(patient_id: str) -> list[dict]:
    """
    Return a list of active MedicationRequest resources for the given patient.
    Each item is a dict with 'id', 'name', and 'dosage' keys.
    """
    resp = requests.get(
        f"{FHIR_BASE_URL}/MedicationRequest",
        headers=get_headers(),
        params={
            "subject": f"Patient/{patient_id}",
            "status": "active",
            "_count": "50",
        },
        timeout=10,
    )
    resp.raise_for_status()

    medications: list[dict] = []
    for entry in resp.json().get("entry", []):
        resource = entry.get("resource", {})
        med_concept = resource.get("medicationCodeableConcept", {})
        name = med_concept.get("text") or next(
            (
                c.get("display")
                for c in med_concept.get("coding", [])
                if c.get("display")
            ),
            None,
        )
        dosage_list = resource.get("dosageInstruction", [])
        dosage = dosage_list[0].get("text") if dosage_list else None
        if name:
            medications.append(
                {
                    "id": resource.get("id", ""),
                    "name": name,
                    "dosage": dosage or "as directed",
                }
            )
    return medications


class MedicationReconciliationController(guava.CallController):
    def __init__(self, patient_name: str, patient_id: str):
        super().__init__()
        self.patient_name = patient_name
        self.patient_id = patient_id
        self.medications: list[dict] = []
        self.still_taking: list[str] = []
        self.stopped: list[str] = []
        self.discrepancies: list[str] = []

        # Pre-fetch active MedicationRequests from Meditech before the call begins
        # so we can present the list to the patient without any mid-call latency.
        try:
            self.medications = fetch_medication_requests(self.patient_id)
            logging.info(
                "Fetched %d active MedicationRequest(s) for patient %s.",
                len(self.medications),
                self.patient_id,
            )
        except Exception as e:
            logging.error(
                "Failed to fetch MedicationRequests for patient %s: %s",
                self.patient_id,
                e,
            )

        self.set_persona(
            organization_name="Valley General Hospital",
            agent_name="Sam",
            agent_purpose=(
                "to conduct a pre-admission medication reconciliation call with patients, "
                "confirming which medications they are currently taking so the clinical team "
                "has an accurate list before admission"
            ),
        )

        self.reach_person(
            contact_full_name=self.patient_name,
            on_success=self.begin_reconciliation,
            on_failure=self.recipient_unavailable,
        )

    def begin_reconciliation(self):
        if not self.medications:
            # No medications on file — still valuable to confirm and document.
            self.set_task(
                objective=(
                    f"Reach {self.patient_name} for a pre-admission medication check. "
                    "There are no active medications on file. Confirm whether they are "
                    "taking any medications not in our system."
                ),
                checklist=[
                    guava.Say(
                        f"Hi {self.patient_name}, this is Sam calling from Valley General Hospital. "
                        "We are reaching out ahead of your upcoming admission to review your "
                        "current medications. We don't currently have any active medications on "
                        "file for you."
                    ),
                    guava.Field(
                        key="taking_any_medications",
                        description=(
                            "Ask the patient whether they are currently taking any medications, "
                            "vitamins, or supplements — including over-the-counter products. "
                            "Capture 'yes' or 'no'."
                        ),
                        field_type="multiple_choice",
                        choices=["yes", "no"],
                        required=True,
                    ),
                    guava.Field(
                        key="unlisted_medications",
                        description=(
                            "If the patient said yes, ask them to list the medications they are "
                            "currently taking. Capture their full response. "
                            "If they said no, capture 'none'."
                        ),
                        field_type="text",
                        required=True,
                    ),
                ],
                on_complete=self.handle_no_medications_on_file,
            )
            return

        # Build a spoken list of medications on file to present to the patient.
        med_lines = [
            f"{i + 1}. {m['name']} — {m['dosage']}"
            for i, m in enumerate(self.medications)
        ]
        med_list_spoken = "; ".join(med_lines)

        self.set_task(
            objective=(
                f"Review active medications on file with {self.patient_name} ahead of their "
                "admission to Valley General Hospital. Read the list, confirm which ones they "
                "are still taking, and identify any they have stopped or that are missing."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.patient_name}, this is Sam calling from Valley General Hospital. "
                    "We are reaching out ahead of your upcoming admission to confirm the "
                    "medications we have on file for you. Our records show the following "
                    f"active medications: {med_list_spoken}. "
                    "I'd like to go through these with you to make sure everything is accurate."
                ),
                guava.Field(
                    key="still_taking_all",
                    description=(
                        "Ask the patient whether they are currently taking all of the medications "
                        "that were just listed. Capture 'yes — taking all of them', "
                        "'no — stopped one or more', or 'partially — some but not all'."
                    ),
                    field_type="multiple_choice",
                    choices=[
                        "yes, taking all of them",
                        "no, stopped one or more",
                        "partially, some but not all",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="stopped_medications",
                    description=(
                        "If the patient stopped or is not taking some medications, ask them to "
                        "name which ones they are no longer taking and briefly why if they know. "
                        "Capture their full response. If they are taking all medications, "
                        "capture 'none'."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="additional_medications",
                    description=(
                        "Ask whether the patient is currently taking any medications, vitamins, "
                        "or supplements that were NOT on the list that was read to them — "
                        "including over-the-counter products. "
                        "Capture their full response, or 'none' if there are no additions."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="allergy_changes",
                    description=(
                        "Ask whether the patient has developed any new medication allergies or "
                        "adverse reactions since their last visit. Capture 'yes' or 'no', "
                        "and if yes, ask them to name the medication and describe the reaction."
                    ),
                    field_type="text",
                    required=True,
                ),
            ],
            on_complete=self.process_reconciliation,
        )

    def handle_no_medications_on_file(self):
        taking_any = self.get_field("taking_any_medications")
        unlisted = self.get_field("unlisted_medications")

        note_text = (
            f"Pre-admission medication reconciliation — no active medications on file. "
            f"Patient reports taking medications: {taking_any}. "
            f"Medications reported by patient: {unlisted}."
        )

        self._save_reconciliation_note(note_text, has_discrepancies=taking_any == "yes")

        self.hangup(
            final_instructions=(
                f"Thank {self.patient_name} for their time. "
                + (
                    "Let them know their medication information has been recorded and the "
                    "admissions team at Valley General Hospital will review it before their "
                    "arrival. Remind them to bring all of their medication bottles or a written "
                    "list to the hospital on the day of admission. "
                    if taking_any == "yes"
                    else "Let them know their record has been noted and the care team will "
                    "have everything ready for their admission. "
                )
                + "Wish them well and thank them for calling Valley General Hospital."
            )
        )

    def process_reconciliation(self):
        still_taking_all = self.get_field("still_taking_all")
        stopped_medications = self.get_field("stopped_medications")
        additional_medications = self.get_field("additional_medications")
        allergy_changes = self.get_field("allergy_changes")

        # Identify discrepancies: medications stopped or new medications not on file.
        has_stopped = still_taking_all and still_taking_all.strip().lower() in (
            "no, stopped one or more",
            "partially, some but not all",
        )
        has_additions = (
            additional_medications
            and additional_medications.strip().lower() not in ("none", "no", "")
        )
        has_new_allergies = allergy_changes and allergy_changes.strip().lower() not in (
            "no",
            "none",
            "",
        )
        has_discrepancies = has_stopped or has_additions or has_new_allergies

        med_names_on_file = [m["name"] for m in self.medications]

        note_text = (
            f"Pre-admission medication reconciliation completed on "
            f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')} via Guava voice agent (Sam). "
            f"Medications on file reviewed: {'; '.join(med_names_on_file)}. "
            f"Patient taking all: {still_taking_all}. "
            f"Stopped medications: {stopped_medications}. "
            f"Additional medications reported: {additional_medications}. "
            f"Allergy or adverse reaction changes: {allergy_changes}. "
            f"Discrepancies flagged: {'yes' if has_discrepancies else 'no'}."
        )

        self._save_reconciliation_note(note_text, has_discrepancies=has_discrepancies)

        if has_discrepancies:
            self.hangup(
                final_instructions=(
                    f"Thank {self.patient_name} for going through this with us. "
                    "Let them know we have noted the differences between our records and what "
                    "they reported today. Assure them that a member of the clinical team at "
                    "Valley General Hospital will review and reconcile the medication list before "
                    "their admission. Remind them to bring all of their medication bottles or a "
                    "written list to the hospital on the day of admission — this helps the team "
                    "provide the safest possible care. Thank them and wish them well."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Thank {self.patient_name} for confirming their medication information. "
                    "Let them know their medication list has been verified and the care team at "
                    "Valley General Hospital will have everything ready for their admission. "
                    "Remind them to bring their medications or a written list on the day of "
                    "their visit. Wish them well."
                )
            )

    def _save_reconciliation_note(self, note_text: str, has_discrepancies: bool):
        """
        Save the reconciliation summary as a FHIR DocumentReference in Meditech Expanse.
        The note is stored as a base64-encoded plain-text attachment so it appears
        in the patient's clinical document timeline and can be reviewed by the admissions team.
        """
        import base64

        encoded_note = base64.b64encode(note_text.encode("utf-8")).decode("ascii")
        now = datetime.now(timezone.utc).isoformat()

        doc_ref = {
            "resourceType": "DocumentReference",
            "status": "current",
            "type": {
                "coding": [
                    {
                        "system": "http://loinc.org",
                        "code": "56445-0",
                        "display": "Medication summary Document",
                    }
                ],
                "text": "Medication Reconciliation Note",
            },
            "category": [
                {
                    "coding": [
                        {
                            "system": "http://hl7.org/fhir/us/core/CodeSystem/us-core-documentreference-category",
                            "code": "clinical-note",
                            "display": "Clinical Note",
                        }
                    ]
                }
            ],
            "subject": {"reference": f"Patient/{self.patient_id}"},
            "date": now,
            "author": [{"display": "Guava Voice Agent — Sam (Valley General Hospital)"}],
            "description": (
                "Pre-admission medication reconciliation"
                + (" — discrepancies flagged" if has_discrepancies else " — confirmed")
            ),
            "content": [
                {
                    "attachment": {
                        "contentType": "text/plain",
                        "data": encoded_note,
                        "title": "Medication Reconciliation Summary",
                        "creation": now,
                    }
                }
            ],
        }

        try:
            resp = requests.post(
                f"{FHIR_BASE_URL}/DocumentReference",
                headers=get_headers(),
                json=doc_ref,
                timeout=10,
            )
            resp.raise_for_status()
            doc_id = resp.json().get("id", "")
            logging.info(
                "Reconciliation note saved as DocumentReference %s for patient %s.",
                doc_id,
                self.patient_id,
            )
        except Exception as e:
            logging.error(
                "Failed to save reconciliation DocumentReference for patient %s: %s",
                self.patient_id,
                e,
            )

    def recipient_unavailable(self):
        self.hangup(
            final_instructions=(
                f"Leave a brief, professional voicemail for {self.patient_name} on behalf of "
                "Valley General Hospital. Let them know we called to review their medications "
                "ahead of their upcoming admission. Ask them to call us back at their earliest "
                "convenience. Keep the message concise and under 30 seconds."
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Outbound pre-admission medication reconciliation call for Valley General Hospital "
            "via Meditech Expanse FHIR."
        )
    )
    parser.add_argument(
        "phone",
        help="Patient phone number to call (E.164 format, e.g. +15551234567)",
    )
    parser.add_argument("--name", required=True, help="Full name of the patient")
    parser.add_argument(
        "--patient-id",
        required=True,
        help="Meditech Expanse Patient FHIR resource ID",
    )
    args = parser.parse_args()

    logging.info(
        "Initiating medication reconciliation call to %s (%s), patient ID: %s",
        args.name,
        args.phone,
        args.patient_id,
    )

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=MedicationReconciliationController(
            patient_name=args.name,
            patient_id=args.patient_id,
        ),
    )
