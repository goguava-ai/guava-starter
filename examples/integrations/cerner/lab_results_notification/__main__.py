import guava
import os
import logging
from guava import logging_utils
import argparse
import requests
from datetime import datetime, timezone


CERNER_FHIR_BASE_URL = os.environ["CERNER_FHIR_BASE_URL"]
CERNER_ACCESS_TOKEN = os.environ["CERNER_ACCESS_TOKEN"]

FHIR_HEADERS = {
    "Authorization": f"Bearer {CERNER_ACCESS_TOKEN}",
    "Accept": "application/fhir+json",
    "Content-Type": "application/fhir+json",
}


def get_patient(patient_id: str) -> dict | None:
    resp = requests.get(
        f"{CERNER_FHIR_BASE_URL}/Patient/{patient_id}",
        headers=FHIR_HEADERS,
        timeout=10,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def get_lab_observations(patient_id: str, observation_ids: list[str]) -> list:
    """Fetches specific Observation resources by ID."""
    observations = []
    for obs_id in observation_ids:
        try:
            resp = requests.get(
                f"{CERNER_FHIR_BASE_URL}/Observation/{obs_id}",
                headers=FHIR_HEADERS,
                timeout=10,
            )
            if resp.status_code == 200:
                observations.append(resp.json())
        except Exception as e:
            logging.warning("Could not fetch observation %s: %s", obs_id, e)
    return observations


def format_observation(obs: dict) -> str:
    """Returns a plain-language description of a lab observation."""
    display = obs.get("code", {}).get("text") or obs.get("code", {}).get("coding", [{}])[0].get("display", "Lab result")
    value_qty = obs.get("valueQuantity")
    value_str = obs.get("valueString")
    value_code = obs.get("valueCodeableConcept", {}).get("text")

    if value_qty:
        value = f"{value_qty.get('value')} {value_qty.get('unit', '')}".strip()
    elif value_str:
        value = value_str
    elif value_code:
        value = value_code
    else:
        value = "result available"

    interpretation = obs.get("interpretation", [{}])[0].get("text") or \
                     obs.get("interpretation", [{}])[0].get("coding", [{}])[0].get("display", "")
    interp_note = f" ({interpretation})" if interpretation else ""

    return f"{display}: {value}{interp_note}"


def create_communication(patient_id: str, note: str) -> None:
    """Creates a FHIR Communication resource to log the notification."""
    resource = {
        "resourceType": "Communication",
        "status": "completed",
        "category": [{"coding": [{"code": "notification"}]}],
        "subject": {"reference": f"Patient/{patient_id}"},
        "payload": [{"contentString": note}],
        "sent": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "medium": [{"text": "Phone"}],
    }
    resp = requests.post(
        f"{CERNER_FHIR_BASE_URL}/Communication",
        headers=FHIR_HEADERS,
        json=resource,
        timeout=10,
    )
    resp.raise_for_status()


class LabResultsNotificationController(guava.CallController):
    def __init__(self, patient_id: str, patient_name: str, observation_ids: list[str], provider_name: str):
        super().__init__()
        self.patient_id = patient_id
        self.patient_name = patient_name
        self.observation_ids = observation_ids
        self.provider_name = provider_name
        self.results_summary = []

        # Fetch lab results pre-call to personalize the notification.
        try:
            observations = get_lab_observations(patient_id, observation_ids)
            self.results_summary = [format_observation(o) for o in observations]
        except Exception as e:
            logging.error("Failed to fetch lab observations pre-call: %s", e)

        has_results = bool(self.results_summary)

        self.set_persona(
            organization_name="Riverside Health System",
            agent_name="Sam",
            agent_purpose=(
                "to notify patients that their lab results are available and answer "
                "any questions they have about next steps"
            ),
        )

        self.reach_person(
            contact_full_name=patient_name,
            on_success=self.deliver_results,
            on_failure=self.recipient_unavailable,
        )

    def deliver_results(self):
        results_text = (
            "The following results are now available: " + "; ".join(self.results_summary) + "."
            if self.results_summary
            else "Your lab results from your recent visit are now available."
        )

        self.set_task(
            objective=(
                f"Notify {self.patient_name} that their lab results are ready, share a "
                "summary if available, and answer questions about next steps."
            ),
            checklist=[
                guava.Say(
                    f"Hi, may I speak with {self.patient_name}? "
                    f"This is Sam calling from Riverside Health System on behalf of "
                    f"Dr. {self.provider_name}."
                ),
                guava.Say(
                    f"I'm calling to let you know that your lab results are ready. {results_text} "
                    "Dr. {self.provider_name} has reviewed these results and would like to discuss "
                    "them with you at your next visit."
                ),
                guava.Field(
                    key="understood",
                    field_type="multiple_choice",
                    description="Ask if they received and understood the notification.",
                    choices=["yes, understood", "has questions"],
                    required=True,
                ),
                guava.Field(
                    key="questions",
                    field_type="text",
                    description=(
                        "If they have questions, ask them to share. "
                        "Answer general questions about next steps. For clinical interpretation, "
                        "note that the provider will discuss in detail at the appointment."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="wants_appointment",
                    field_type="multiple_choice",
                    description=(
                        "Ask if they'd like to schedule a follow-up appointment to discuss "
                        "the results with the provider."
                    ),
                    choices=["yes", "no, I have an upcoming appointment", "no thanks"],
                    required=True,
                ),
            ],
            on_complete=self.log_notification,
        )

    def log_notification(self):
        understood = self.get_field("understood") or "yes, understood"
        questions = self.get_field("questions") or ""
        wants_appt = self.get_field("wants_appointment") or "no thanks"

        log_note = (
            f"Lab results notification call — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n"
            f"Patient: {self.patient_name}\n"
            f"Results shared: {'; '.join(self.results_summary) if self.results_summary else 'results available'}\n"
            f"Patient understood: {understood}\n"
            f"Appointment requested: {wants_appt}"
        )
        if questions:
            log_note += f"\nQuestions: {questions}"

        logging.info(
            "Lab notification complete for patient %s — understood: %s, appt wanted: %s",
            self.patient_id, understood, wants_appt,
        )

        try:
            create_communication(self.patient_id, log_note)
            logging.info("FHIR Communication resource created for patient %s.", self.patient_id)
        except Exception as e:
            logging.error("Failed to create FHIR Communication: %s", e)

        if wants_appt == "yes":
            self.hangup(
                final_instructions=(
                    f"Let {self.patient_name} know the scheduling team will call them back within "
                    "one business day to book a follow-up appointment. Thank them for their time "
                    "and wish them good health."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Thank {self.patient_name} for their time. Remind them that their full results "
                    "are available in their patient portal and that Dr. {self.provider_name} will "
                    "discuss them at their upcoming visit. Wish them good health."
                )
            )

    def recipient_unavailable(self):
        logging.info("Unable to reach %s for lab results notification.", self.patient_name)
        try:
            create_communication(
                self.patient_id,
                f"Lab results notification attempted — {self.patient_name} unavailable, voicemail left. "
                f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            )
        except Exception as e:
            logging.error("Failed to create Communication for voicemail: %s", e)

        self.hangup(
            final_instructions=(
                f"Leave a brief, professional voicemail for {self.patient_name} from Riverside "
                "Health System. Let them know their lab results are ready and they can view them "
                "in their patient portal. Ask them to call back if they have questions. "
                "Do not mention specific results in the voicemail."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound lab results notification call via Cerner FHIR."
    )
    parser.add_argument("phone", help="Patient's phone number (E.164, e.g. +15551234567)")
    parser.add_argument("--patient-id", required=True, help="FHIR Patient resource ID")
    parser.add_argument("--name", required=True, help="Patient's full name")
    parser.add_argument("--observation-ids", nargs="+", required=True, help="FHIR Observation resource IDs to share")
    parser.add_argument("--provider", required=True, help="Ordering provider's last name")
    args = parser.parse_args()

    logging.info(
        "Initiating lab results notification call to %s (%s)", args.name, args.phone,
    )

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=LabResultsNotificationController(
            patient_id=args.patient_id,
            patient_name=args.name,
            observation_ids=args.observation_ids,
            provider_name=args.provider,
        ),
    )
