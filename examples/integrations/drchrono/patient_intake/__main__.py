import guava
import os
import logging
import requests

logging.basicConfig(level=logging.INFO)

ACCESS_TOKEN = os.environ["DRCHRONO_ACCESS_TOKEN"]
DOCTOR_ID = int(os.environ["DRCHRONO_DOCTOR_ID"])
OFFICE_ID = int(os.environ["DRCHRONO_OFFICE_ID"])
HEADERS = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
BASE_URL = "https://app.drchrono.com/api"


def create_patient(
    first_name: str,
    last_name: str,
    date_of_birth: str,
    email: str,
    cell_phone: str,
) -> dict:
    """Create a new patient record in DrChrono."""
    resp = requests.post(
        f"{BASE_URL}/patients",
        headers=HEADERS,
        json={
            "first_name": first_name,
            "last_name": last_name,
            "date_of_birth": date_of_birth,
            "email": email,
            "cell_phone": cell_phone,
            "doctor": DOCTOR_ID,
            "office": OFFICE_ID,
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def update_patient(patient_id: int, data: dict) -> dict:
    """Update supplemental fields on an existing patient record."""
    resp = requests.patch(
        f"{BASE_URL}/patients/{patient_id}",
        headers=HEADERS,
        json=data,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


class PatientIntakeController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Oakridge Family Medicine",
            agent_name="Alex",
            agent_purpose=(
                "to collect new patient intake information before their first appointment "
                "at Oakridge Family Medicine"
            ),
        )

        self.set_task(
            objective=(
                "A new patient is calling Oakridge Family Medicine to complete their intake. "
                "Collect their demographic information, insurance details, and primary care concern "
                "so that a patient record can be created before their first visit."
            ),
            checklist=[
                guava.Say(
                    "Thank you for calling Oakridge Family Medicine. "
                    "My name is Alex and I'll be helping you complete your new patient intake today. "
                    "This should only take a few minutes."
                ),
                guava.Field(
                    key="first_name",
                    field_type="text",
                    description="Ask for the caller's first name.",
                    required=True,
                ),
                guava.Field(
                    key="last_name",
                    field_type="text",
                    description="Ask for the caller's last name.",
                    required=True,
                ),
                guava.Field(
                    key="date_of_birth",
                    field_type="text",
                    description=(
                        "Ask for their date of birth. Capture in YYYY-MM-DD format."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="email",
                    field_type="text",
                    description="Ask for their email address for appointment communications.",
                    required=True,
                ),
                guava.Field(
                    key="cell_phone",
                    field_type="text",
                    description="Ask for their cell phone number for appointment reminders.",
                    required=True,
                ),
                guava.Field(
                    key="insurance_carrier",
                    field_type="text",
                    description=(
                        "Ask for the name of their health insurance carrier, for example Blue Cross or Aetna. "
                        "This is optional — skip if they are uninsured or prefer not to share."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="insurance_member_id",
                    field_type="text",
                    description=(
                        "If they provided an insurance carrier, ask for their member ID or policy number "
                        "found on their insurance card. Skip if they did not provide a carrier."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="primary_care_concern",
                    field_type="text",
                    description=(
                        "Ask what their primary health concern is — the main reason they are "
                        "seeking care at Oakridge Family Medicine."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="allergies",
                    field_type="text",
                    description=(
                        "Ask if they have any known allergies, such as to medications or foods. "
                        "This is optional — they can say 'none' or skip."
                    ),
                    required=False,
                ),
            ],
            on_complete=self.handle_complete,
        )

        self.accept_call()

    def handle_complete(self):
        first_name = self.get_field("first_name") or ""
        last_name = self.get_field("last_name") or ""
        dob = self.get_field("date_of_birth") or ""
        email = self.get_field("email") or ""
        cell_phone = self.get_field("cell_phone") or ""
        insurance_carrier = self.get_field("insurance_carrier") or ""
        insurance_member_id = self.get_field("insurance_member_id") or ""
        primary_care_concern = self.get_field("primary_care_concern") or ""
        allergies = self.get_field("allergies") or ""

        patient_id = None
        try:
            patient = create_patient(
                first_name=first_name,
                last_name=last_name,
                date_of_birth=dob,
                email=email,
                cell_phone=cell_phone,
            )
            patient_id = patient.get("id")
            logging.info(
                "Created patient record for %s %s — ID: %s",
                first_name, last_name, patient_id,
            )
        except Exception as e:
            logging.error("Failed to create patient record: %s", e)

        # Log supplemental details that don't have direct DrChrono fields in POST /patients
        logging.info(
            "Intake details — Insurance: %s / %s | Concern: %s | Allergies: %s",
            insurance_carrier, insurance_member_id, primary_care_concern, allergies,
        )

        if patient_id:
            self.hangup(
                final_instructions=(
                    f"Let {first_name} know their patient record has been created at Oakridge Family Medicine. "
                    f"Tell them their patient ID is {patient_id} — they can reference this number in the future. "
                    "Let them know the care team will reach out to schedule their first appointment. "
                    "Thank them for taking the time to complete their intake and wish them a great day."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Apologize to {first_name or 'the caller'} and let them know there was a technical issue "
                    "creating their patient record. Ask them to call back or stay on the line "
                    "while a team member assists. Thank them for their patience."
                )
            )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=PatientIntakeController,
    )
