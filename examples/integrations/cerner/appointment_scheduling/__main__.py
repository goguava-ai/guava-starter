import guava
import os
import logging
import requests
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)

CERNER_FHIR_BASE_URL = os.environ["CERNER_FHIR_BASE_URL"]
CERNER_ACCESS_TOKEN = os.environ["CERNER_ACCESS_TOKEN"]

FHIR_HEADERS = {
    "Authorization": f"Bearer {CERNER_ACCESS_TOKEN}",
    "Accept": "application/fhir+json",
    "Content-Type": "application/fhir+json",
}

# Practitioner IDs to route appointment types to — configure for your org.
PRACTITIONER_MAP = {
    "primary care": os.environ.get("CERNER_PRACTITIONER_PCP", ""),
    "specialist": os.environ.get("CERNER_PRACTITIONER_SPECIALIST", ""),
    "urgent care": os.environ.get("CERNER_PRACTITIONER_URGENT", ""),
    "follow-up": os.environ.get("CERNER_PRACTITIONER_PCP", ""),
    "lab / blood draw": os.environ.get("CERNER_PRACTITIONER_LAB", ""),
    "imaging": os.environ.get("CERNER_PRACTITIONER_IMAGING", ""),
}

SLOT_OFFSETS = {
    "tomorrow morning": (1, 9),
    "tomorrow afternoon": (1, 14),
    "day after tomorrow morning": (2, 9),
    "day after tomorrow afternoon": (2, 14),
    "next available": (3, 10),
}


def find_patient_by_mrn(mrn: str) -> dict | None:
    resp = requests.get(
        f"{CERNER_FHIR_BASE_URL}/Patient",
        headers=FHIR_HEADERS,
        params={"identifier": mrn},
        timeout=10,
    )
    resp.raise_for_status()
    entries = resp.json().get("entry", [])
    return entries[0].get("resource") if entries else None


def create_appointment(
    patient_id: str,
    practitioner_id: str,
    appt_type: str,
    reason: str,
    slot_key: str,
) -> dict:
    """Creates a FHIR Appointment resource. Returns the created resource."""
    day_offset, hour = SLOT_OFFSETS.get(slot_key, (3, 10))
    start_dt = datetime.utcnow().replace(hour=hour, minute=0, second=0, microsecond=0) + timedelta(days=day_offset)
    end_dt = start_dt + timedelta(minutes=30)

    participants = [
        {
            "actor": {"reference": f"Patient/{patient_id}"},
            "status": "accepted",
        }
    ]
    if practitioner_id:
        participants.append(
            {
                "actor": {"reference": f"Practitioner/{practitioner_id}"},
                "status": "accepted",
            }
        )

    resource = {
        "resourceType": "Appointment",
        "status": "booked",
        "appointmentType": {
            "coding": [{"system": "http://terminology.hl7.org/CodeSystem/v2-0276", "code": "ROUTINE"}],
            "text": appt_type,
        },
        "reasonReference": [{"display": reason}],
        "start": start_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "end": end_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "comment": f"Scheduled via voice agent — {datetime.utcnow().strftime('%Y-%m-%d')}",
        "participant": participants,
    }

    resp = requests.post(
        f"{CERNER_FHIR_BASE_URL}/Appointment",
        headers=FHIR_HEADERS,
        json=resource,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


class AppointmentSchedulingController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Riverside Health System",
            agent_name="Sam",
            agent_purpose=(
                "to help Riverside Health System patients schedule medical appointments "
                "quickly and conveniently"
            ),
        )

        self.set_task(
            objective=(
                "A patient has called to schedule an appointment. Verify their identity, "
                "understand the type of appointment needed, capture their preferred time, "
                "and book it in the EHR."
            ),
            checklist=[
                guava.Say(
                    "Thank you for calling Riverside Health System. I'm Sam, and I can help "
                    "you schedule an appointment. Let me pull up your record first."
                ),
                guava.Field(
                    key="mrn",
                    field_type="text",
                    description=(
                        "Ask for their medical record number (MRN). Let them know it's on their "
                        "patient portal or any previous paperwork."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="date_of_birth",
                    field_type="text",
                    description="Ask for their date of birth to verify their identity.",
                    required=True,
                ),
                guava.Field(
                    key="appointment_type",
                    field_type="multiple_choice",
                    description="Ask what type of appointment they need.",
                    choices=[
                        "primary care",
                        "specialist",
                        "urgent care",
                        "follow-up",
                        "lab / blood draw",
                        "imaging",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="reason_for_visit",
                    field_type="text",
                    description=(
                        "Ask for a brief description of the reason for the visit. "
                        "Keep it high-level — this helps route to the right provider."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="preferred_slot",
                    field_type="multiple_choice",
                    description="Ask when they'd like to come in.",
                    choices=[
                        "tomorrow morning",
                        "tomorrow afternoon",
                        "day after tomorrow morning",
                        "day after tomorrow afternoon",
                        "next available",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="insurance_confirmed",
                    field_type="multiple_choice",
                    description=(
                        "Ask if their insurance information is up to date in our system, "
                        "or if they need to update it."
                    ),
                    choices=["yes, it's current", "no, I need to update it"],
                    required=True,
                ),
            ],
            on_complete=self.book_appointment,
        )

        self.accept_call()

    def book_appointment(self):
        mrn = (self.get_field("mrn") or "").strip()
        dob = self.get_field("date_of_birth") or ""
        appt_type = self.get_field("appointment_type") or "primary care"
        reason = self.get_field("reason_for_visit") or "general visit"
        slot = self.get_field("preferred_slot") or "next available"
        insurance = self.get_field("insurance_confirmed") or "yes, it's current"

        logging.info("Looking up patient MRN: %s", mrn)
        patient = None
        try:
            patient = find_patient_by_mrn(mrn)
        except Exception as e:
            logging.error("Patient lookup failed: %s", e)

        if not patient:
            self.hangup(
                final_instructions=(
                    "Let the caller know you couldn't locate their record with that MRN and date of birth. "
                    "Ask them to double-check their MRN from their patient portal, or offer to transfer "
                    "them to the front desk. Be patient and empathetic."
                )
            )
            return

        patient_id = patient.get("id", "")
        name_entry = (patient.get("name") or [{}])[0]
        given = " ".join(name_entry.get("given", []))
        family = name_entry.get("family", "")
        patient_name = f"{given} {family}".strip() or "the patient"

        practitioner_id = PRACTITIONER_MAP.get(appt_type, "")

        logging.info("Booking %s appointment for patient %s — slot: %s", appt_type, patient_id, slot)
        try:
            appt = create_appointment(patient_id, practitioner_id, appt_type, reason, slot)
            appt_id = appt.get("id", "")
            appt_start = appt.get("start", "")[:16].replace("T", " ") + " UTC"
            logging.info("Appointment created: %s at %s", appt_id, appt_start)

            insurance_note = (
                " We'll also note that their insurance information needs to be updated — "
                "ask them to bring their current insurance card to the appointment."
                if insurance == "no, I need to update it" else ""
            )

            self.hangup(
                final_instructions=(
                    f"Let {patient_name} know their {appt_type} appointment has been scheduled. "
                    f"The time is {appt_start}. "
                    + (f"Appointment ID: {appt_id}. " if appt_id else "")
                    + "Let them know they'll receive a confirmation via the patient portal. "
                    "Ask them to arrive 15 minutes early and bring a photo ID."
                    + insurance_note
                    + " Thank them for calling Riverside Health System."
                )
            )
        except Exception as e:
            logging.error("Failed to create FHIR Appointment: %s", e)
            self.hangup(
                final_instructions=(
                    f"Apologize to {patient_name} for a technical issue. Let them know the scheduling "
                    "team will call them back within two hours to complete the booking. "
                    "Thank them for their patience."
                )
            )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=AppointmentSchedulingController,
    )
