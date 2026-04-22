import guava
import os
import logging
from guava import logging_utils
import argparse
import requests


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


agent = guava.Agent(
    name="Taylor",
    organization="Oakridge Family Medicine",
    purpose=(
        "to notify patients that their lab results are available "
        "and connect them with the right next step"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    lab_doc_id = call.get_variable("lab_doc_id")

    # Fetch lab document details
    lab_doc = None
    try:
        lab_doc = get_lab_document(lab_doc_id)
        logging.info(
            "Fetched lab document %s: description=%s, lab_name=%s, date=%s",
            lab_doc_id,
            lab_doc.get("description"),
            lab_doc.get("lab_name"),
            lab_doc.get("document_date"),
        )
    except Exception as e:
        logging.error("Failed to fetch lab document %s pre-call: %s", lab_doc_id, e)

    description = lab_doc.get("description", "lab work") if lab_doc else "lab work"
    lab_name = lab_doc.get("lab_name", "") if lab_doc else ""
    document_date = lab_doc.get("document_date", "") if lab_doc else ""

    call.set_variable("lab_description", description)
    call.set_variable("lab_name", lab_name)
    call.set_variable("lab_date", document_date)

    call.reach_person(contact_full_name=patient_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    patient_name = call.get_variable("patient_name")
    lab_description = call.get_variable("lab_description") or "lab work"
    lab_name = call.get_variable("lab_name") or ""
    lab_date = call.get_variable("lab_date") or ""

    if outcome == "unavailable":
        logging.info("Unable to reach %s for lab results notification.", patient_name)
        call.hangup(
            final_instructions=(
                f"Leave a brief voicemail for {patient_name} from Oakridge Family Medicine. "
                "Let them know you're calling to notify them that their lab results are now available. "
                "Do not mention any specific values or findings. "
                "Ask them to call back or log in to the patient portal to review. "
                "Keep it concise and friendly."
            )
        )
    elif outcome == "available":
        lab_clause = f" from {lab_name}" if lab_name else ""
        date_clause = f" dated {lab_date}" if lab_date else ""

        # IMPORTANT: Do NOT read out actual lab values or results over the phone.
        # Only notify the patient that results are available and guide them to review securely.
        call.set_task(
            "save_results",
            objective=(
                f"Notify {patient_name} that their {lab_description} results{lab_clause}{date_clause} "
                "are now available at Oakridge Family Medicine. "
                "Do not share or discuss the actual lab values — only confirm the results are in. "
                "Find out if they received the notification, whether they want an appointment to review, "
                "and how they prefer to be contacted."
            ),
            checklist=[
                guava.Say(
                    f"Hi {patient_name}, this is Taylor calling from Oakridge Family Medicine. "
                    f"I'm calling to let you know that your {lab_description} results"
                    + (f" from {lab_name}" if lab_name else "")
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
        )


@agent.on_task_complete("save_results")
def on_save_results(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    patient_id = call.get_variable("patient_id")
    lab_doc_id = call.get_variable("lab_doc_id")
    lab_description = call.get_variable("lab_description") or "lab work"

    acknowledged = call.get_field("acknowledged") or "yes"
    wants_appointment = call.get_field("wants_appointment") or "no"
    preferred_contact = call.get_field("preferred_contact_method") or "phone"

    # Update lab document status to patient_notified
    try:
        mark_lab_notified(lab_doc_id)
        logging.info("Lab document %s marked as patient_notified", lab_doc_id)
    except Exception as e:
        logging.error("Failed to update lab document %s status: %s", lab_doc_id, e)

    # Log the call
    notes = (
        f"Lab results notification call to {patient_name} for lab document {lab_doc_id} "
        f"({lab_description}). "
        f"Patient acknowledged: {acknowledged}. "
        f"Wants appointment: {wants_appointment}. "
        f"Preferred contact method: {preferred_contact}."
    )
    try:
        log_call(patient_id, notes)
        logging.info("Call logged for patient %s", patient_id)
    except Exception as e:
        logging.error("Failed to log call for patient %s: %s", patient_id, e)

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

    call.hangup(
        final_instructions=(
            f"Thank {patient_name} for confirming. "
            + appointment_followup
            + contact_instructions
            + " Remind them they can always call Oakridge Family Medicine with any questions. "
            "Wish them a great day."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
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

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "patient_name": args.name,
            "patient_id": args.patient_id,
            "lab_doc_id": args.lab_doc_id,
        },
    )
