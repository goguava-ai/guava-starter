# SDK conformance: guava-sdk 0.44.0 (2026-09-15)
import argparse
import json
import logging
import os
from datetime import datetime, timezone

import guava
from guava import logging_utils
from guava.helpers.llm import IntentRecognizer
from guava.events import BotSessionEnded, OutboundCallFailed


# ---------------------------------------------------------------------------
# Mock API — simulates patient records and pre-authorization backend
# ---------------------------------------------------------------------------

MOCK_PATIENTS = {
    "MRN-40210": {
        "patient": "Elena Vasquez",
        "dob": "1980-02-14",
        "insurance_provider": "Blue Cross Blue Shield",
        "insurance_id": "BCB-994102",
        "policy_status": "active",
    },
    "MRN-40211": {
        "patient": "James Okafor",
        "dob": "1975-09-30",
        "insurance_provider": "Aetna",
        "insurance_id": "AET-338471",
        "policy_status": "active",
    },
    "MRN-40212": {
        "patient": "Patricia Nguyen",
        "dob": "1988-12-05",
        "insurance_provider": "United Healthcare",
        "insurance_id": "UHC-220198",
        "policy_status": "active",
    },
}

MOCK_AUTH_RESULTS = {
    "MRN-40210": {
        "decision": "approved",
        "auth_number": "PA-2026-88410",
        "valid_through": "2026-10-01",
        "notes": "Approved for the requested procedure. No additional documentation required.",
    },
    "MRN-40211": {
        "decision": "pending",
        "auth_number": None,
        "valid_through": None,
        "notes": "Additional clinical notes are required from the ordering provider. Expected review timeline is 3 to 5 business days after receipt.",
    },
    "MRN-40212": {
        "decision": "needs_more_info",
        "auth_number": None,
        "valid_through": None,
        "required_docs": ["operative report", "recent lab results", "letter of medical necessity"],
        "notes": "The insurance carrier requires additional documentation before a determination can be made.",
    },
}

BENEFITS_COORDINATOR_LINE = "+15551000400"


def verify_patient(mrn, dob):
    patient = MOCK_PATIENTS.get(mrn)
    if patient and patient["dob"] == dob:
        return patient
    return None


def check_preauth(mrn):
    return MOCK_AUTH_RESULTS.get(mrn)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

agent = guava.Agent(
    name="Casey",
    organization="Riverside Medical Center",
    purpose=(
        "contact patients to verify their identity, collect procedure and "
        "insurance information for an upcoming procedure, and share the "
        "pre-authorization determination from their insurance carrier"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
    "speak_to_benefits": "The caller wants to speak to a benefits coordinator or billing representative",
})


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(
        contact_full_name=call.get_variable("patient_name"),
        voicemail_message=(
            f"Hi, this is Casey from Riverside Medical Center calling for "
            f"{call.get_variable('patient_name')}. We have an update for you. "
            f"Please call us back at 555-0150 at your convenience. Thank you."
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    patient_name = call.get_variable("patient_name")

    if outcome == "available":
        call.set_task(
            "verify_identity",
            objective=(
                f"Verify the identity of {patient_name} before sharing any "
                f"information about their procedure or insurance authorization. "
                f"Ask for their date of birth. Do not discuss any clinical or "
                f"insurance details until identity is confirmed."
            ),
            checklist=[
                guava.Say(
                    "I'm calling with an update regarding an upcoming procedure. "
                    "Before I share any details, I need to verify your identity."
                ),
                guava.Field(
                    key="dob",
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
                "contacted again by phone, and that any updates will be sent by mail, and politely say goodbye."
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
    dob = call.get_field("dob")
    patient = verify_patient(mrn, dob)

    if patient is None:
        logging.warning("Identity verification failed for MRN %s.", mrn)
        call.hangup(
            final_instructions=(
                "Let them know the date of birth provided does not match our "
                "records. For their privacy, you cannot share any details. "
                "Suggest they call the billing office at 555-0150 with their "
                "medical record number handy, and politely say goodbye."
            )
        )
        return

    patient_name = call.get_variable("patient_name")

    call.add_info("patient_record", {
        "mrn": mrn,
        "insurance_provider": patient["insurance_provider"],
        "insurance_id": patient["insurance_id"],
    })

    call.set_task(
        "collect_procedure_info",
        objective=(
            f"Identity verified for {patient_name}. Confirm the procedure they "
            f"are scheduled for and verify their insurance information on file. "
            f"Their insurance is {patient['insurance_provider']} with member ID "
            f"{patient['insurance_id']}. Ask if this is still current. "
            f"Do NOT provide any coverage advice or predict authorization outcomes. "
            f"Your insurance company will make the final determination."
        ),
        checklist=[
            guava.Say(
                f"Thank you, {patient_name}. Your identity has been verified. "
                f"I have your insurance on file as {patient['insurance_provider']}, "
                f"member ID {patient['insurance_id']}. Is that still current?"
            ),
            guava.Field(
                key="insurance_confirmed",
                description="Whether the patient confirms the insurance information on file is current",
                field_type="multiple_choice",
                choices=["yes", "needs_update"],
                required=True,
            ),
            guava.Field(
                key="updated_insurance",
                description=(
                    "If the patient's insurance has changed, collect the new "
                    "insurance provider name and member ID. Skip if confirmed."
                ),
                field_type="text",
                required=False,
            ),
            guava.Field(
                key="procedure_confirmed",
                description=(
                    "Ask the patient what procedure they are scheduled for."
                ),
                field_type="text",
                required=True,
            ),
        ],
    )


@agent.on_task_complete("collect_procedure_info")
def on_procedure_info_collected(call: guava.Call) -> None:
    mrn = call.get_variable("mrn")
    patient_name = call.get_variable("patient_name")
    auth_result = check_preauth(mrn)

    if auth_result is None:
        call.hangup(
            final_instructions=(
                f"Let {patient_name} know that we do not have an authorization "
                f"result on file yet. A benefits coordinator will follow up within "
                f"2 business days, and thank them for their time, and politely say goodbye."
            )
        )
        return

    call.set_variable("auth_decision", auth_result["decision"])
    decision = auth_result["decision"]

    if decision == "approved":
        call.set_task(
            "deliver_auth_result",
            objective=(
                f"Share the pre-authorization result with {patient_name}. The "
                f"authorization has been approved. The authorization number is "
                f"{auth_result['auth_number']}, valid through {auth_result['valid_through']}. "
                f"Do NOT provide any coverage advice — your insurance company will "
                f"make the final determination on coverage amounts and copays."
            ),
            checklist=[
                guava.Say(
                    f"Good news — the pre-authorization for your procedure has been "
                    f"approved by your insurance carrier."
                ),
                guava.Field(
                    key="auth_understood",
                    description="Whether the patient understood the authorization details",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="has_questions",
                    description="Whether the patient has any questions about the authorization or next steps",
                    field_type="multiple_choice",
                    choices=["yes", "no"],
                    required=True,
                ),
            ],
        )
    elif decision == "pending":
        call.set_task(
            "deliver_auth_result",
            objective=(
                f"Share the pre-authorization status with {patient_name}. The "
                f"authorization is currently pending. {auth_result['notes']} "
                f"Do NOT predict the outcome or provide coverage advice — your "
                f"insurance company will make the final determination."
            ),
            checklist=[
                guava.Say(
                    f"I wanted to let you know that your pre-authorization is "
                    f"currently pending review with your insurance carrier."
                ),
                guava.Field(
                    key="auth_understood",
                    description="Whether the patient understood the pending status and timeline",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="has_questions",
                    description="Whether the patient has questions about the timeline or process",
                    field_type="multiple_choice",
                    choices=["yes", "no"],
                    required=True,
                ),
            ],
        )
    else:
        required_docs = auth_result.get("required_docs", [])
        docs_list = ", ".join(required_docs) if required_docs else "additional documentation"
        call.set_task(
            "deliver_auth_result",
            objective=(
                f"Share the pre-authorization status with {patient_name}. The "
                f"insurance carrier needs additional information before making a "
                f"determination. The required documents are: {docs_list}. "
                f"Explain clearly what is needed and offer to connect them with "
                f"a benefits coordinator for help. "
                f"Do NOT provide any coverage advice — your insurance company will "
                f"make the final determination."
            ),
            checklist=[
                guava.Say(
                    f"Your insurance carrier has reviewed the request and needs "
                    f"some additional documentation before they can make a "
                    f"determination."
                ),
                guava.Field(
                    key="auth_understood",
                    description="Whether the patient understood what additional documents are needed",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="has_questions",
                    description="Whether the patient has questions or wants to speak to a benefits coordinator",
                    field_type="multiple_choice",
                    choices=["yes", "no"],
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("deliver_auth_result")
def on_auth_delivered(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    has_questions = call.get_field("has_questions")

    if has_questions == "yes":
        call.transfer(
            destination=BENEFITS_COORDINATOR_LINE,
            instructions=(
                f"Let {patient_name} know you are connecting them with a benefits "
                f"coordinator who can assist with their questions. Let them know "
                f"all the information collected so far has been saved."
            ),
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {patient_name} for their time. Remind them they can call "
                f"the billing office at 555-0150 if any questions come up. Wish "
                f"them well, and politely say goodbye."
            )
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
            "again by phone and that future updates will be sent by mail, and politely say goodbye."
        )
    )


@agent.on_action("speak_to_benefits")
def handle_transfer_request(call: guava.Call) -> None:
    call.transfer(
        destination=BENEFITS_COORDINATOR_LINE,
        instructions=(
            "Let them know you are connecting them with a benefits coordinator now. "
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
        "use_case": "insurance_preauth",
        "patient_name": call.get_variable("patient_name"),
        "mrn": call.get_variable("mrn"),
        "auth_decision": call.get_variable("auth_decision"),
        "dob_verified": call.get_field("dob") is not None,
        "insurance_confirmed": call.get_field("insurance_confirmed"),
        "procedure_confirmed": call.get_field("procedure_confirmed"),
        "auth_understood": call.get_field("auth_understood"),
        "has_questions": call.get_field("has_questions"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound insurance pre-authorization update for Riverside Medical Center"
    )
    parser.add_argument("phone", help="Patient phone number to call")
    parser.add_argument("--name", required=True, help="Full name of the patient")
    parser.add_argument(
        "--mrn",
        required=True,
        help="Medical record number (try MRN-40210, MRN-40211, or MRN-40212)",
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
