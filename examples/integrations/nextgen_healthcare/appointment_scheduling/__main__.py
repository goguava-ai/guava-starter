import guava
import os
import logging
from guava import logging_utils
import json
import requests
from datetime import datetime



def get_access_token() -> str:
    resp = requests.post(
        os.environ["NEXTGEN_TOKEN_URL"],
        data={"grant_type": "client_credentials", "scope": "system/*.read system/*.write"},
        auth=(os.environ["NEXTGEN_CLIENT_ID"], os.environ["NEXTGEN_CLIENT_SECRET"]),
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def search_patients(last_name: str, dob: str, headers: dict) -> list:
    base_url = os.environ["NEXTGEN_BASE_URL"]
    resp = requests.get(
        f"{base_url}/Patient",
        headers=headers,
        params={"family": last_name, "birthdate": dob},
        timeout=10,
    )
    if not resp.ok:
        return []
    return resp.json().get("entry", [])


def search_slots(start_date: str, service_type: str, headers: dict) -> list:
    base_url = os.environ["NEXTGEN_BASE_URL"]
    resp = requests.get(
        f"{base_url}/Slot",
        headers=headers,
        params={"start": f"ge{start_date}", "status": "free", "service-type": service_type, "_count": "5"},
        timeout=10,
    )
    if not resp.ok:
        return []
    return resp.json().get("entry", [])


def post_appointment(patient_id: str | None, patient_display: str, slot: dict, reason: str, headers: dict) -> dict | None:
    base_url = os.environ["NEXTGEN_BASE_URL"]
    slot_id = slot.get("id", "")
    slot_start = slot.get("start", "")
    slot_end = slot.get("end", "")

    participant = (
        [{"actor": {"reference": f"Patient/{patient_id}"}, "status": "accepted"}]
        if patient_id else
        [{"actor": {"display": patient_display}, "status": "accepted"}]
    )

    payload = {
        "resourceType": "Appointment",
        "status": "booked",
        "serviceType": [{"text": reason}],
        "start": slot_start,
        "end": slot_end,
        "slot": [{"reference": f"Slot/{slot_id}"}],
        "participant": participant,
        "comment": f"Booked via phone — {patient_display}",
    }
    resp = requests.post(f"{base_url}/Appointment", headers=headers, json=payload, timeout=10)
    if not resp.ok:
        return None
    return resp.json()


class AppointmentSchedulingController(guava.CallController):
    def __init__(self):
        super().__init__()
        self.patient_id = None
        self.selected_slot = None
        self.headers = {}

        try:
            token = get_access_token()
            self.headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        except Exception as e:
            logging.error("Token error at startup: %s", e)

        self.set_persona(
            organization_name="Metro Specialty Clinic",
            agent_name="Morgan",
            agent_purpose=(
                "to help patients schedule appointments at Metro Specialty Clinic"
            ),
        )

        self.set_task(
            objective=(
                "A patient has called Metro Specialty Clinic to schedule an appointment. "
                "Collect their identifying information and preferences."
            ),
            checklist=[
                guava.Say(
                    "Thank you for calling Metro Specialty Clinic scheduling. "
                    "This is Morgan. I'd be happy to help you book an appointment today."
                ),
                guava.Field(
                    key="first_name",
                    field_type="text",
                    description="Ask for their first name.",
                    required=True,
                ),
                guava.Field(
                    key="last_name",
                    field_type="text",
                    description="Ask for their last name.",
                    required=True,
                ),
                guava.Field(
                    key="date_of_birth",
                    field_type="text",
                    description="Ask for their date of birth (YYYY-MM-DD).",
                    required=True,
                ),
                guava.Field(
                    key="reason_for_visit",
                    field_type="text",
                    description="Ask what brings them in — new patient visit, follow-up, specialist consult, etc.",
                    required=True,
                ),
                guava.Field(
                    key="preferred_date",
                    field_type="text",
                    description="Ask what date they prefer (YYYY-MM-DD).",
                    required=True,
                ),
            ],
            on_complete=self.find_slot,
        )

        self.accept_call()

    def find_slot(self):
        first_name = self.get_field("first_name")
        last_name = self.get_field("last_name")
        dob = self.get_field("date_of_birth")
        reason = self.get_field("reason_for_visit")
        preferred_date = self.get_field("preferred_date")

        logging.info("Scheduling: %s %s, DOB %s, reason: %s, date: %s",
                     first_name, last_name, dob, reason, preferred_date)

        try:
            patients = search_patients(last_name, dob, self.headers)
            if patients:
                self.patient_id = patients[0]["resource"]["id"]
                logging.info("Found patient: %s", self.patient_id)
        except Exception as e:
            logging.warning("Patient search failed: %s", e)

        try:
            slots = search_slots(preferred_date, reason, self.headers)
            if slots:
                self.selected_slot = slots[0]["resource"]
                slot_start = self.selected_slot.get("start", "")
                try:
                    dt = datetime.fromisoformat(slot_start.replace("Z", "+00:00"))
                    display_time = dt.strftime("%A, %B %-d at %-I:%M %p")
                except (ValueError, AttributeError):
                    display_time = slot_start

                self.set_task(
                    objective=f"Present the available slot to {first_name} and confirm.",
                    checklist=[
                        guava.Say(f"I found an opening on {display_time}. Would that work for you?"),
                        guava.Field(
                            key="confirmed",
                            field_type="multiple_choice",
                            description="Ask if they'd like to book this slot.",
                            choices=["yes", "no"],
                            required=True,
                        ),
                    ],
                    on_complete=lambda: self.book_slot(first_name, last_name, reason, display_time),
                )
                return
        except Exception as e:
            logging.error("Slot search failed: %s", e)

        self.hangup(
            final_instructions=(
                f"Apologize to {first_name} — no slots available near their preferred date. "
                "Let them know a scheduler will call back within one business day. "
                "Thank them for calling Metro Specialty Clinic."
            )
        )

    def book_slot(self, first_name: str, last_name: str, reason: str, display_time: str):
        confirmed = self.get_field("confirmed") or ""
        if confirmed.lower() != "yes":
            self.hangup(
                final_instructions=(
                    f"Acknowledge that {first_name} would prefer a different time. "
                    "Let them know a scheduler will follow up with options. Thank them for calling."
                )
            )
            return

        appointment = None
        try:
            appointment = post_appointment(
                self.patient_id,
                f"{first_name} {last_name}",
                self.selected_slot,
                reason,
                self.headers,
            )
            logging.info("Appointment booked: %s", appointment.get("id") if appointment else None)
        except Exception as e:
            logging.error("Booking failed: %s", e)

        if appointment:
            print(json.dumps({"appointment_id": appointment.get("id"), "display_time": display_time}, indent=2))
            self.hangup(
                final_instructions=(
                    f"Confirm to {first_name} that their appointment has been booked for {display_time} "
                    "at Metro Specialty Clinic. Remind them to arrive 10 minutes early with their "
                    "insurance card and photo ID. They'll receive a confirmation. "
                    "Thank them and wish them a great day."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Apologize to {first_name} — the booking couldn't be completed. "
                    "Let them know a scheduler will call them back to confirm manually. "
                    "Thank them for their patience."
                )
            )


if __name__ == "__main__":
    logging_utils.configure_logging()
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=AppointmentSchedulingController,
    )
