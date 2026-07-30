# SDK conformance: guava-sdk 0.35.0 (2026-07-21)
import argparse
import json
import logging
import os
from datetime import datetime, timezone

import guava
from guava import logging_utils
from guava.helpers.llm import IntentRecognizer

NURSE_TRIAGE_LINE = "+15551000600"


# ---------------------------------------------------------------------------
# Mock API — simulates patient record and discharge instructions
# ---------------------------------------------------------------------------

MOCK_PATIENTS = {
    "MRN-90300": {
        "patient": "William Torres",
        "dob": "1968-01-22",
        "discharge_date": "2026-07-20",
        "diagnosis": "knee replacement surgery",
        "pcp": "Dr. Kapoor",
        "pcp_followup_due": "2026-08-03",
        "medications": [
            {"name": "Oxycodone 5mg", "schedule": "every 6 hours as needed for pain"},
            {"name": "Aspirin 81mg", "schedule": "once daily"},
            {"name": "Cephalexin 500mg", "schedule": "twice daily for 10 days"},
        ],
        "discharge_instructions": (
            "Keep incision clean and dry. Ice 20 minutes on, 20 minutes off. "
            "Begin physical therapy within one week. Elevate leg when resting. "
            "Call if fever exceeds 101F or if redness or swelling worsens."
        ),
    },
    "MRN-90301": {
        "patient": "Angela Foster",
        "dob": "1954-07-09",
        "discharge_date": "2026-07-22",
        "diagnosis": "pneumonia",
        "pcp": "Dr. Lin",
        "pcp_followup_due": "2026-08-01",
        "medications": [
            {"name": "Azithromycin 250mg", "schedule": "once daily for 5 days"},
            {"name": "Guaifenesin 600mg", "schedule": "twice daily as needed"},
            {"name": "Prednisone 20mg", "schedule": "taper per discharge instructions"},
        ],
        "discharge_instructions": (
            "Complete full course of antibiotics. Use incentive spirometer 10 times "
            "per hour while awake. Rest and drink plenty of fluids. Seek immediate "
            "care if breathing becomes difficult or fever returns above 101F."
        ),
    },
    "MRN-90302": {
        "patient": "Kevin Pham",
        "dob": "1990-11-15",
        "discharge_date": "2026-07-23",
        "diagnosis": "appendectomy",
        "pcp": "Dr. Kapoor",
        "pcp_followup_due": "2026-08-06",
        "medications": [
            {"name": "Ibuprofen 400mg", "schedule": "every 6 hours as needed for pain"},
            {"name": "Docusate 100mg", "schedule": "twice daily"},
        ],
        "discharge_instructions": (
            "No heavy lifting for 4 weeks. Incision care: keep dry for 48 hours, "
            "then gentle washing is fine. Normal diet can resume. Call if you "
            "develop fever, increasing abdominal pain, or redness at the incision site."
        ),
    },
}


def lookup_patient(mrn):
    return MOCK_PATIENTS.get(mrn)


def normalize_date(date_str):
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%B %d, %Y", "%B %d %Y", "%b %d, %Y", "%m-%d-%Y"):
        try:
            return datetime.strptime(date_str.strip().rstrip("."), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# Red-flag symptom classification
# ---------------------------------------------------------------------------

_symptom_classifier = IntentRecognizer({
    "emergency": (
        "The patient reports chest pain, difficulty breathing, severe or "
        "uncontrolled bleeding, loss of consciousness, or stroke symptoms "
        "such as facial drooping, arm weakness, or speech difficulty"
    ),
    "urgent": (
        "The patient reports fever above 101F, worsening pain not controlled "
        "by medication, new or unexpected symptoms, signs of infection such as "
        "redness, swelling, or discharge at a surgical site, or persistent vomiting"
    ),
    "routine": (
        "The patient reports mild discomfort, general questions about recovery, "
        "minor soreness, or routine post-procedure symptoms that are expected"
    ),
})


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

agent = guava.Agent(
    name="Sam",
    organization="Riverside Medical Center",
    purpose=(
        "follow up with recently discharged patients to verify their identity, "
        "check on symptoms and recovery, confirm medication adherence, and "
        "ensure they have a PCP follow-up scheduled"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
    "speak_to_nurse": "The caller wants to speak to a nurse, doctor, or clinical staff member",
})


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(
        contact_full_name=call.get_variable("patient_name"),
        voicemail_message=(
            f"Hi, this is Sam from Riverside Medical Center calling for "
            f"{call.get_variable('patient_name')}. We're reaching out to check "
            f"on you after your recent visit. Please call us back at 555-0170 "
            f"at your convenience. Thank you."
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    patient_name = call.get_variable("patient_name")

    if outcome == "available":
        call.set_task(
            "verify_identity",
            objective=(
                f"Verify the identity of {patient_name} before discussing any "
                f"clinical information. Ask for their date of birth. Do NOT "
                f"mention diagnosis, medications, or discharge details until "
                f"identity is confirmed."
            ),
            checklist=[
                guava.Say(
                    "I'm following up after your recent stay with us. Before we "
                    "go any further, I need to verify your identity."
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
                "contacted again by phone, and politely say goodbye."
            )
        )
    elif outcome == "wrong_number":
        logging.info("Wrong number for %s.", patient_name)
        call.hangup(final_instructions="Apologize for the mistake and wish them well, and politely say goodbye.")
    else:
        logging.info("Could not reach %s (outcome: %s).", patient_name, outcome)
        call.hangup()


@agent.on_task_complete("verify_identity")
def on_identity_verified(call: guava.Call) -> None:
    mrn = call.get_variable("mrn")
    dob = call.get_field("date_of_birth")
    patient = lookup_patient(mrn)
    normalized_dob = normalize_date(dob) if dob else None

    if patient is None or normalized_dob != patient["dob"]:
        logging.warning("Identity verification failed for MRN %s.", mrn)
        call.hangup(
            final_instructions=(
                "Let them know the information provided does not match our "
                "records. For their privacy, you cannot continue. Suggest they "
                "call the clinic directly at 555-0170, and politely say goodbye."
            )
        )
        return

    patient_name = call.get_variable("patient_name")

    # Only load clinical context AFTER identity is verified
    med_summary = "; ".join(
        f"{m['name']} ({m['schedule']})" for m in patient["medications"]
    )
    call.add_info("discharge_context", {
        "mrn": mrn,
        "discharge_date": patient["discharge_date"],
        "diagnosis": patient["diagnosis"],
        "pcp": patient["pcp"],
        "pcp_followup_due": patient["pcp_followup_due"],
        "medications": med_summary,
        "discharge_instructions": patient["discharge_instructions"],
    })

    call.set_variable("pcp", patient["pcp"])
    call.set_variable("pcp_followup_due", patient["pcp_followup_due"])
    call.set_variable("medications", patient["medications"])

    call.set_task(
        "symptom_check",
        objective=(
            f"Identity verified for {patient_name}. They were discharged on "
            f"{patient['discharge_date']} following {patient['diagnosis']}. "
            f"Ask how they are feeling overall. Listen carefully — if they "
            f"report emergency symptoms such as chest pain, difficulty "
            f"breathing, or severe bleeding, immediately instruct them to "
            f"call 9-1-1. Do NOT attempt to manage emergency symptoms."
        ),
        checklist=[
            guava.Say(
                f"Thank you, {patient_name}. I can see you were discharged on "
                f"{patient['discharge_date']}. I'd like to check in on how your "
                f"recovery is going."
            ),
            guava.Field(
                key="overall_recovery",
                description=(
                    "How the patient describes their overall recovery — in their "
                    "own words"
                ),
                field_type="text",
                required=True,
            ),
        ],
    )


@agent.on_task_complete("symptom_check")
def on_symptom_general_done(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    call.set_task(
        "symptom_details",
        objective=(
            f"Now collect specific symptom details from {patient_name}. "
            f"Ask about pain level and then about any fever, swelling, or "
            f"trouble breathing since discharge."
        ),
        checklist=[
            guava.Field(
                key="pain_level",
                description=(
                    "The patient's current pain level on a scale of 0 to 10, "
                    "where 0 is no pain and 10 is the worst pain imaginable"
                ),
                field_type="integer",
                required=True,
            ),
            guava.Field(
                key="current_symptoms",
                description=(
                    "Any other symptoms since discharge — specifically fever, "
                    "swelling, or trouble breathing. Capture details."
                ),
                field_type="text",
                required=True,
            ),
        ],
    )


@agent.on_task_complete("symptom_details")
def on_symptom_details_done(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    symptoms = call.get_field("current_symptoms") or ""
    pain_level = call.get_field("pain_level")

    # Classify symptom severity
    severity = _symptom_classifier.classify(symptoms)

    if severity == "emergency":
        logging.critical(
            "EMERGENCY symptoms reported by %s: %s", patient_name, symptoms
        )
        call.set_variable("symptom_severity", "emergency")
        call.hangup(
            final_instructions=(
                f"This is urgent. {patient_name} has reported symptoms that may "
                f"require emergency care. Clearly and calmly instruct them to "
                f"call 9-1-1 immediately or go to the nearest emergency room. "
                f"Do NOT attempt to manage these symptoms over the phone. "
                f"Do NOT transfer — tell them to hang up and call 9-1-1 right now, and politely say goodbye."
            )
        )
        return

    if severity == "urgent" or (isinstance(pain_level, int) and pain_level >= 7):
        logging.warning(
            "Urgent symptoms reported by %s: %s (pain: %s)",
            patient_name, symptoms, pain_level,
        )
        call.set_variable("symptom_severity", "urgent")
        call.set_task(
            "medication_adherence",
            objective=(
                f"{patient_name} has reported concerning symptoms that need "
                f"clinical review. Before transferring to the nurse line, quickly "
                f"check their medication adherence so the triage nurse has a "
                f"complete picture."
            ),
            checklist=[
                guava.Say(
                    f"I want to make sure your care team has a complete picture. "
                    f"Let me quickly ask about your medications before I connect "
                    f"you with a nurse."
                ),
                guava.Field(
                    key="medication_adherence",
                    description=(
                        "For each medication the patient was discharged with, "
                        "ask if they have been taking it as prescribed. Note any "
                        "missed doses or side effects."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="missed_doses",
                    description="Whether the patient has missed any doses of any medication",
                    field_type="multiple_choice",
                    choices=["yes", "no"],
                    required=True,
                ),
                guava.Field(
                    key="side_effects",
                    description="Any side effects the patient has experienced from their medications",
                    field_type="text",
                    required=False,
                ),
            ],
        )
    else:
        call.set_variable("symptom_severity", "routine")
        call.set_task(
            "medication_adherence",
            objective=(
                f"{patient_name}'s symptoms appear routine. Check their medication "
                f"adherence by reviewing each medication from their discharge list."
            ),
            checklist=[
                guava.Say(
                    f"That sounds like your recovery is on track. Now I'd like to "
                    f"go through your medications to make sure everything is going "
                    f"smoothly."
                ),
                guava.Field(
                    key="medication_adherence",
                    description=(
                        "For each medication the patient was discharged with, "
                        "ask if they have been taking it as prescribed. Note any "
                        "missed doses or issues."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="missed_doses",
                    description="Whether the patient has missed any doses of any medication",
                    field_type="multiple_choice",
                    choices=["yes", "no"],
                    required=True,
                ),
                guava.Field(
                    key="side_effects",
                    description="Any side effects the patient has experienced from their medications",
                    field_type="text",
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("medication_adherence")
def on_medication_adherence_done(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    severity = call.get_variable("symptom_severity")
    pcp = call.get_variable("pcp")
    pcp_followup_due = call.get_variable("pcp_followup_due")

    if severity == "urgent":
        call.transfer(
            destination=NURSE_TRIAGE_LINE,
            instructions=(
                f"{patient_name} has reported symptoms that need clinical "
                f"assessment. Connect them with the nurse triage line. Let them "
                f"know their medication information has been recorded and will "
                f"be shared with the nurse."
            ),
        )
        return

    call.set_task(
        "pcp_followup",
        objective=(
            f"Confirm that {patient_name} has a follow-up appointment scheduled "
            f"with {pcp}. Their follow-up is due by {pcp_followup_due}. If they "
            f"have not scheduled it yet, encourage them to do so promptly."
        ),
        checklist=[
            guava.Field(
                key="followup_scheduled",
                description=(
                    f"Whether the patient has scheduled their follow-up appointment "
                    f"with {pcp}, which is due by {pcp_followup_due}"
                ),
                field_type="multiple_choice",
                choices=["yes", "no", "needs_help_scheduling"],
                required=True,
            ),
            guava.Field(
                key="additional_concerns",
                description=(
                    "Any other questions or concerns the patient wants to mention "
                    "for their care team"
                ),
                field_type="text",
                required=False,
            ),
        ],
    )


@agent.on_task_complete("pcp_followup")
def on_pcp_followup_done(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    followup = call.get_field("followup_scheduled")

    if followup == "needs_help_scheduling":
        call.hangup(
            final_instructions=(
                f"Let {patient_name} know that someone from the scheduling team "
                f"will call them within one business day to help book their "
                f"follow-up appointment. Thank them for their time and wish them "
                f"a continued recovery, and politely say goodbye."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {patient_name} for taking the time to check in. Let them "
                f"know all of their responses have been recorded and will be "
                f"reviewed by their care team. Remind them to call 555-0170 if "
                f"any concerns come up, and wish them a speedy recovery, and politely say goodbye."
            )
        )


@agent.on_question
def on_question(call: guava.Call, question: str) -> str:
    return (
        "I want to make sure your care team addresses that — I'll flag it in "
        "your notes. For now, let's continue with the check-in so we have "
        "everything documented."
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
        destination=NURSE_TRIAGE_LINE,
        instructions=(
            "Let them know you are connecting them with a nurse now. "
            "Reassure them that all information collected so far has been saved."
        ),
    )


@agent.on_outbound_failed
def on_outbound_failed(event: guava.OutboundCallFailed) -> None:
    logging.error("Outbound call failed: %s (code %d)", event.error_reason, event.error_code)


@agent.on_session_end
def on_session_end(call: guava.Call, event: guava.BotSessionEnded) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "use_case": "post_discharge_followup",
        "patient_name": call.get_variable("patient_name"),
        "mrn": call.get_variable("mrn"),
        "identity_verified": call.get_field("date_of_birth") is not None,
        "symptom_severity": call.get_variable("symptom_severity"),
        "assessment": {
            "overall_recovery": call.get_field("overall_recovery"),
            "current_symptoms": call.get_field("current_symptoms"),
            "pain_level": call.get_field("pain_level"),
        },
        "medication_compliance": {
            "adherence": call.get_field("medication_adherence"),
            "missed_doses": call.get_field("missed_doses"),
            "side_effects": call.get_field("side_effects"),
        },
        "followup": {
            "followup_scheduled": call.get_field("followup_scheduled"),
            "additional_concerns": call.get_field("additional_concerns"),
        },
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound post-discharge follow-up call for Riverside Medical Center"
    )
    parser.add_argument("phone", help="Patient phone number to call")
    parser.add_argument("--name", required=True, help="Full name of the patient")
    parser.add_argument(
        "--mrn",
        required=True,
        help="Medical record number (try MRN-90300, MRN-90301, or MRN-90302)",
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
