import guava
import os
import logging
import argparse
import requests

logging.basicConfig(level=logging.INFO)

ACCESS_TOKEN = os.environ["DRCHRONO_ACCESS_TOKEN"]
DOCTOR_ID = int(os.environ["DRCHRONO_DOCTOR_ID"])
OFFICE_ID = int(os.environ["DRCHRONO_OFFICE_ID"])
HEADERS = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
BASE_URL = "https://app.drchrono.com/api"


def get_lab_document(lab_doc_id: str) -> dict:
    """Fetch a lab document by ID to get description, lab name, and date."""
    resp = requests.get(
        f"{BASE_URL}/lab_documents/{lab_doc_id}",
        headers=HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def mark_lab_notified(lab_doc_id: str) -> dict:
    """Update the lab document status to 'patient_notified'."""
    resp = requests.patch(
        f"{BASE_URL}/lab_documents/{lab_doc_id}",
        headers=HEADERS,
        json={"status": "patient_notified"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def log_call(patient_id: str, notes: str) -> dict:
    """Log the outbound call in DrChrono."""
    resp = requests.post(
        f"{BASE_URL}/call_logs",
        headers=HEADERS,
        json={
            "patient": int(patient_id),
            "notes": notes,
            "called_by": DOCTOR_ID,
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


class LabResultsNotificationController(guava.CallController):
    def __init__(self, patient_name: str, patient_id: str, lab_doc_id: str):
        super().__init__()
        self.patient_name = patient_name
        self.patient_id = patient_id
        self.lab_doc_id = lab_doc_id
        self.lab_doc = None

        # Pre-call: fetch lab document details
        try:
            self.lab_doc = get_lab_document(lab_doc_id)
            logging.info(
                "Fetched lab document %s: description=%s, lab_name=%s, date=%s",
                lab_doc_id,
                self.lab_doc.get("description"),
                self.lab_doc.get("lab_name"),
                self.lab_doc.get("document_date"),
            )
        except Exception as e:
            logging.error("Failed to fetch lab document %s pre-call: %s", lab_doc_id, e)

        description = self.lab_doc.get("description", "lab work") if self.lab_doc else "lab work"
        lab_name = self.lab_doc.get("lab_name", "") if self.lab_doc else ""
        document_date = self.lab_doc.get("document_date", "") if self.lab_doc else ""

        self.lab_description = description
        self.lab_name = lab_name
        self.lab_date = document_date

        self.set_persona(
            organization_name="Oakridge Family Medicine",
            agent_name="Taylor",
            agent_purpose=(
                "to notify patients that their lab results are available "
                "and connect them with the right next step"
            ),
        )

        self.reach_person(
            contact_full_name=patient_name,
            on_success=self.begin_call,
            on_failure=self.recipient_unavailable,
        )

    def begin_call(self):
        lab_clause = f" from {self.lab_name}" if self.lab_name else ""
        date_clause = f" dated {self.lab_date}" if self.lab_date else ""

        # IMPORTANT: Do NOT read out actual lab values or results over the phone.
        # Only notify the patient that results are available and guide them to review securely.
        self.set_task(
            objective=(
                f"Notify {self.patient_name} that their {self.lab_description} results{lab_clause}{date_clause} "
                "are now available at Oakridge Family Medicine. "
                "Do not share or discuss the actual lab values — only confirm the results are in. "
                "Find out if they received the notification, whether they want an appointment to review, "
                "and how they prefer to be contacted."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.patient_name}, this is Taylor calling from Oakridge Family Medicine. "
                    f"I'm calling to let you know that your {self.lab_description} results"
                    + (f" from {self.lab_name}" if self.lab_name else "")
                    + " are now available. "
                    "Your doctor will be happy to review them with you. "
                    "I'm not able to go over the specific values on this call, "
                    "but I can help you figure out the best way to access them."
                ),
                guava.Field(
                    key="acknowledged",
                    field_type="multiple_choice",
                    description=(
                        "Confirm that the patient has heard the notification that their results are available. "
                        "Ask: 'Have you received this notification?' Options: yes or no."
                    ),
                    choices=["yes", "no"],
                    required=True,
                ),
                guava.Field(
                    key="wants_appointment",
                    field_type="multiple_choice",
                    description=(
                        "Ask whether they would like to schedule an appointment to review the results "
                        "with their doctor, or if they've already scheduled one."
                    ),
                    choices=["yes", "no", "already-scheduled"],
                    required=True,
                ),
                guava.Field(
                    key="preferred_contact_method",
                    field_type="multiple_choice",
                    description=(
                        "Ask how they would prefer to receive their results or follow-up communications: "
                        "by phone, through the patient portal, or by mail."
                    ),
                    choices=["phone", "portal", "mail"],
                    required=True,
                ),
            ],
            on_complete=self.save_results,
        )

    def save_results(self):
        acknowledged = self.get_field("acknowledged") or "yes"
        wants_appointment = self.get_field("wants_appointment") or "no"
        preferred_contact = self.get_field("preferred_contact_method") or "phone"

        # Update lab document status to patient_notified
        try:
            mark_lab_notified(self.lab_doc_id)
            logging.info("Lab document %s marked as patient_notified", self.lab_doc_id)
        except Exception as e:
            logging.error("Failed to update lab document %s status: %s", self.lab_doc_id, e)

        # Log the call
        notes = (
            f"Lab results notification call to {self.patient_name} for lab document {self.lab_doc_id} "
            f"({self.lab_description}). "
            f"Patient acknowledged: {acknowledged}. "
            f"Wants appointment: {wants_appointment}. "
            f"Preferred contact method: {preferred_contact}."
        )
        try:
            log_call(self.patient_id, notes)
            logging.info("Call logged for patient %s", self.patient_id)
        except Exception as e:
            logging.error("Failed to log call for patient %s: %s", self.patient_id, e)

        appointment_followup = ""
        if wants_appointment == "yes":
            appointment_followup = (
                "Let them know a team member will call them to schedule an appointment "
                "to review the results with their doctor. "
            )
        elif wants_appointment == "already-scheduled":
            appointment_followup = (
                "Acknowledge that they already have an appointment scheduled "
                "and confirm the results will be ready for that visit. "
            )

        contact_instructions = {
            "phone": "Let them know the office will call them with any follow-up.",
            "portal": "Encourage them to log in to the patient portal to view their results securely.",
            "mail": "Let them know a summary will be mailed to the address on file.",
        }.get(preferred_contact, "")

        self.hangup(
            final_instructions=(
                f"Thank {self.patient_name} for confirming. "
                + appointment_followup
                + contact_instructions
                + " Remind them they can always call Oakridge Family Medicine with any questions. "
                "Wish them a great day."
            )
        )

    def recipient_unavailable(self):
        logging.info("Unable to reach %s for lab results notification.", self.patient_name)
        self.hangup(
            final_instructions=(
                f"Leave a brief voicemail for {self.patient_name} from Oakridge Family Medicine. "
                "Let them know you're calling to notify them that their lab results are now available. "
                "Do not mention any specific values or findings. "
                "Ask them to call back or log in to the patient portal to review. "
                "Keep it concise and friendly."
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Outbound lab results notification call via DrChrono."
    )
    parser.add_argument("phone", help="Patient phone number (E.164, e.g. +15551234567)")
    parser.add_argument("--lab-doc-id", required=True, help="DrChrono lab document ID")
    parser.add_argument("--patient-id", required=True, help="DrChrono patient ID")
    parser.add_argument("--name", required=True, help="Patient's full name")
    args = parser.parse_args()

    logging.info(
        "Sending lab results notification to %s (%s), lab document ID: %s",
        args.name, args.phone, args.lab_doc_id,
    )

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=LabResultsNotificationController(
            patient_name=args.name,
            patient_id=args.patient_id,
            lab_doc_id=args.lab_doc_id,
        ),
    )
