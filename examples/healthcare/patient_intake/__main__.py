# SDK conformance: guava-sdk 0.39.0 (2026-08-26)
import argparse
import json
import logging
import os
from datetime import datetime, timezone

import guava
from guava import logging_utils
from guava.helpers.llm import IntentRecognizer
from guava.events import BotSessionEnded, OutboundCallFailed

NURSE_LINE = "+15551000500"


# ---------------------------------------------------------------------------
# Mock EHR API — simulates patient record lookup and intake submission
# ---------------------------------------------------------------------------

MOCK_PATIENTS = {
    "MRN-80100": {
        "patient": "Grace Tanaka",
        "dob": "1982-05-11",
        "primary_provider": "Dr. Alvarez",
        "upcoming_appointment": "2026-08-05 at 9:30 AM",
        "known_allergies": "Penicillin",
        "active_medications": "Lisinopril 10mg, Metformin 500mg",
    },
    "MRN-80101": {
        "patient": "Robert Williams",
        "dob": "1970-03-28",
        "primary_provider": "Dr. Chen",
        "upcoming_appointment": "2026-08-06 at 2:00 PM",
        "known_allergies": "None on file",
        "active_medications": "None on file",
    },
    "MRN-80102": {
        "patient": "Diana Morales",
        "dob": "1995-08-19",
        "primary_provider": "Dr. Alvarez",
        "upcoming_appointment": "2026-08-07 at 11:00 AM",
        "known_allergies": "Sulfa drugs, Latex",
        "active_medications": "Sertraline 50mg",
    },
}


def lookup_patient(mrn):
    return MOCK_PATIENTS.get(mrn)


def submit_intake(mrn, intake_data):
    logging.info("[MOCK EHR] POST /intake — submitted for MRN %s", mrn)
    return True


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

agent = guava.Agent(
    name="Dana",
    organization="Summit Health Clinic",
    purpose=(
        "conduct pre-visit intake calls to verify patient identity, collect "
        "medical history, current medications, and allergies, and schedule "
        "follow-up care as needed"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
    "speak_to_nurse": "The caller wants to speak to a nurse, provider, or clinical staff member",
})


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(
        contact_full_name=call.get_variable("patient_name"),
        voicemail_message=(
            f"Hi, this is Dana from Summit Health Clinic calling for "
            f"{call.get_variable('patient_name')}. We're reaching out ahead of "
            f"an upcoming appointment. Please call us back at 555-0160 at your "
            f"convenience. Thank you."
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    patient_name = call.get_variable("patient_name")

    if outcome == "available":
        call.set_task(
            "verify_identity",
            objective=(
                f"Verify the identity of {patient_name} before collecting any "
                f"medical information. This is required by our privacy policy. "
                f"Ask for their date of birth. Do NOT collect any health information, "
                f"discuss medications, or mention any clinical details until identity "
                f"is confirmed."
            ),
            checklist=[
                guava.Say(
                    "I'm calling to complete a quick pre-visit intake ahead of "
                    "your upcoming appointment. Before we get started, I need to "
                    "verify your identity."
                ),
                guava.Field(
                    key="date_of_birth",
                    description="The patient's date of birth for identity verification",
                    field_type="text",
                    required=True,
                ),
            ],
        )
    elif outcome == "do_not_contact":
        logging.info("Patient %s requested no further contact.", patient_name)
        call.hangup(
            final_instructions=(
                "Acknowledge their request. Let them know they will not be "
                "contacted again and have been removed from the call list, and politely say goodbye."
            )
        )
    elif outcome == "wrong_number":
        logging.info("Wrong number for %s.", patient_name)
        call.hangup(final_instructions="Apologize for the mistake and wish them well, and politely say goodbye.")
    else:
        logging.info("Could not reach %s (outcome: %s).", patient_name, outcome)
        call.hangup()


@agent.on_validate("date_of_birth")
def validate_dob(call: guava.Call, value) -> bool | tuple[bool, str]:
    if isinstance(value, str) and len(value) >= 8:
        return True
    return (False, "I need your full date of birth, including the month, day, and year.")


@agent.on_task_complete("verify_identity")
def on_identity_verified(call: guava.Call) -> None:
    mrn = call.get_variable("mrn")
    dob = call.get_field("date_of_birth")
    patient = lookup_patient(mrn)

    if patient is None or patient["dob"] != dob:
        logging.warning("Identity verification failed for MRN %s.", mrn)
        call.hangup(
            final_instructions=(
                "Let them know the information provided does not match our "
                "records. For their privacy, you cannot proceed with the intake. "
                "Suggest they call the clinic directly at 555-0160, and politely say goodbye."
            )
        )
        return

    patient_name = call.get_variable("patient_name")

    # Only load patient context AFTER identity is verified
    call.add_info("patient_context", {
        "mrn": mrn,
        "primary_provider": patient["primary_provider"],
        "upcoming_appointment": patient["upcoming_appointment"],
        "known_allergies": patient["known_allergies"],
        "active_medications": patient["active_medications"],
    })

    call.set_task(
        "medical_history",
        objective=(
            f"Identity verified for {patient_name}. Collect their medical "
            f"history for the intake. Ask about any recent hospitalizations, "
            f"surgeries, or significant medical events in the past year. Also "
            f"ask about their family medical history for major conditions."
        ),
        checklist=[
            guava.Say(
                f"Thank you, {patient_name}. Your identity has been verified. "
                f"Now I'll collect some information to help your care team prepare "
                f"for your visit. Everything you share is confidential."
            ),
            guava.Field(
                key="chief_complaint",
                description=(
                    "The primary reason the patient is coming in for this visit. "
                    "What symptoms, concerns, or conditions are they hoping to address?"
                ),
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="recent_hospitalizations",
                description=(
                    "Any hospitalizations, surgeries, or significant medical events "
                    "in the past 12 months. Capture details or note none."
                ),
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="family_history",
                description=(
                    "Relevant family medical history, such as heart disease, "
                    "diabetes, cancer, or other hereditary conditions"
                ),
                field_type="text",
                required=False,
            ),
        ],
    )


@agent.on_task_complete("medical_history")
def on_medical_history_done(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")

    call.set_task(
        "current_medications",
        objective=(
            f"Collect {patient_name}'s current medication information. Review "
            f"what is on file and ask if there have been any changes. Also "
            f"confirm their allergy information is up to date."
        ),
        checklist=[
            guava.Field(
                key="medications_current",
                description=(
                    "All medications the patient is currently taking, including "
                    "prescriptions, over-the-counter medications, vitamins, and "
                    "supplements. Ask if the medications on file are still accurate."
                ),
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="medication_changes",
                description=(
                    "Any recent changes to medications — new prescriptions, "
                    "discontinued medications, or dosage changes"
                ),
                field_type="text",
                required=False,
            ),
            guava.Field(
                key="allergies_confirmed",
                description=(
                    "Confirm the patient's allergy information on file is current. "
                    "Ask if they have any new allergies to medications, foods, "
                    "latex, or environmental factors."
                ),
                field_type="text",
                required=True,
            ),
        ],
    )


@agent.on_task_complete("current_medications")
def on_medications_done(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")

    call.set_task(
        "schedule_followup",
        objective=(
            f"Wrap up the intake for {patient_name}. Ask if they need any "
            f"follow-up care scheduled, such as lab work, imaging, or a "
            f"referral to a specialist. Confirm their preferred pharmacy is "
            f"on file."
        ),
        checklist=[
            guava.Field(
                key="needs_lab_work",
                description="Whether the patient needs any lab work or imaging before the visit",
                field_type="multiple_choice",
                choices=["yes", "no", "not sure"],
                required=True,
            ),
            guava.Field(
                key="preferred_pharmacy",
                description="The patient's preferred pharmacy for any prescriptions",
                field_type="text",
                required=False,
            ),
        ],
    )


@agent.on_task_complete("schedule_followup")
def on_schedule_followup_done(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    call.set_task(
        "check_urgent_symptoms",
        objective=(
            f"Before finishing up, check whether {patient_name} has any "
            f"urgent or concerning symptoms they want to report before their "
            f"visit. If they do, note the symptoms so a nurse can follow up."
        ),
        checklist=[
            guava.Field(
                key="urgent_symptoms",
                description=(
                    "Any urgent or concerning symptoms the patient wants to "
                    "report before their visit"
                ),
                field_type="text",
                required=False,
            ),
        ],
    )


@agent.on_task_complete("check_urgent_symptoms")
def on_urgent_check_done(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    mrn = call.get_variable("mrn")
    urgent = call.get_field("urgent_symptoms")

    # Submit intake to EHR
    intake_data = {
        "chief_complaint": call.get_field("chief_complaint"),
        "recent_hospitalizations": call.get_field("recent_hospitalizations"),
        "family_history": call.get_field("family_history"),
        "medications_current": call.get_field("medications_current"),
        "medication_changes": call.get_field("medication_changes"),
        "allergies_confirmed": call.get_field("allergies_confirmed"),
        "needs_lab_work": call.get_field("needs_lab_work"),
        "preferred_pharmacy": call.get_field("preferred_pharmacy"),
        "urgent_symptoms": urgent,
    }
    submit_intake(mrn, intake_data)

    if urgent and str(urgent).strip():
        call.transfer(
            destination=NURSE_LINE,
            instructions=(
                f"{patient_name} reported urgent symptoms during their intake: "
                f"{urgent}. Connect them with the nurse line so a clinical team "
                f"member can assess. Let them know the rest of their intake has "
                f"been saved."
            ),
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {patient_name} for completing the intake. Let them know "
                f"their information has been securely recorded and the care team "
                f"will review it before their appointment. Remind them to bring "
                f"their insurance card and photo ID, and wish them well, and politely say goodbye."
            )
        )


@agent.on_question
def on_question(call: guava.Call, question: str) -> str:
    return (
        "That's an important question for your provider — I'll make sure they "
        "see it in your intake notes. For now, let's continue so we have "
        "everything ready for your visit."
    )


@agent.on_action_request
def on_action_request(call: guava.Call, intent_summary: str):
    return _mid_call_intent.classify(intent_summary)


@agent.on_action("do_not_contact")
def handle_dnc(call: guava.Call) -> None:
    logging.info("Patient %s requested DNC mid-call.", call.get_variable("patient_name"))
    call.hangup(
        final_instructions=(
            "Acknowledge their request. Let them know they will not be contacted "
            "again by phone, and wish them well, and politely say goodbye."
        )
    )


@agent.on_action("speak_to_nurse")
def handle_nurse_transfer(call: guava.Call) -> None:
    call.transfer(
        destination=NURSE_LINE,
        instructions=(
            "Let them know you are connecting them with the nurse line now. "
            "Reassure them that any information collected so far has been saved."
        ),
    )


@agent.on_outbound_failed
def on_outbound_failed(event: OutboundCallFailed) -> None:
    logging.error("Outbound call failed: %s (code %d)", event.error_reason, event.error_code)


@agent.on_session_end
def on_session_end(call: guava.Call, event: BotSessionEnded) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "use_case": "patient_intake",
        "patient_name": call.get_variable("patient_name"),
        "mrn": call.get_variable("mrn"),
        "identity_verified": call.get_field("date_of_birth") is not None,
        "intake": {
            "chief_complaint": call.get_field("chief_complaint"),
            "recent_hospitalizations": call.get_field("recent_hospitalizations"),
            "family_history": call.get_field("family_history"),
            "medications_current": call.get_field("medications_current"),
            "medication_changes": call.get_field("medication_changes"),
            "allergies_confirmed": call.get_field("allergies_confirmed"),
            "needs_lab_work": call.get_field("needs_lab_work"),
            "preferred_pharmacy": call.get_field("preferred_pharmacy"),
            "urgent_symptoms": call.get_field("urgent_symptoms"),
        },
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound pre-visit patient intake call for Summit Health Clinic"
    )
    parser.add_argument("phone", help="Patient phone number to call")
    parser.add_argument("--name", required=True, help="Full name of the patient")
    parser.add_argument(
        "--mrn",
        required=True,
        help="Medical record number (try MRN-80100, MRN-80101, or MRN-80102)",
    )
    parser.add_argument(
        "--from-number",
        default=os.environ.get("GUAVA_AGENT_NUMBER", ""),
        help="Caller ID / from number (defaults to GUAVA_AGENT_NUMBER env var).",
    )
    args = parser.parse_args()

    agent.call_phone(
        from_number=args.from_number,
        to_number=args.phone,
        variables={
            "patient_name": args.name,
            "mrn": args.mrn,
        },
    )
