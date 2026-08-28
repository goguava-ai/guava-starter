# SDK conformance: guava-sdk 0.40.0 (2026-08-26)
import argparse
import json
import logging
import os
from datetime import datetime, timezone

import guava
from guava import logging_utils
from guava.helpers.llm import IntentRecognizer
from guava.events import BotSessionEnded, OutboundCallFailed

PHARMACY_LINE = "+15551000700"


# ---------------------------------------------------------------------------
# Mock API — simulates prescription lookup
# ---------------------------------------------------------------------------

MOCK_PATIENTS = {
    "MRN-70400": {
        "patient": "Thomas Bradley",
        "dob": "1965-08-12",
        "prescriptions": [
            {
                "rx_number": "RX-881001",
                "medication": "Atorvastatin 20mg",
                "refills_remaining": 3,
                "status": "available",
                "pharmacy": "Cornerstone Pharmacy — Main Street",
                "controlled": False,
            },
            {
                "rx_number": "RX-881002",
                "medication": "Metoprolol 50mg",
                "refills_remaining": 0,
                "status": "needs_renewal",
                "pharmacy": "Cornerstone Pharmacy — Main Street",
                "controlled": False,
            },
        ],
    },
    "MRN-70401": {
        "patient": "Keisha Robinson",
        "dob": "1983-04-25",
        "prescriptions": [
            {
                "rx_number": "RX-881003",
                "medication": "Adderall 10mg",
                "refills_remaining": 0,
                "status": "controlled_substance",
                "pharmacy": "Maple Street Drugs — Oak Avenue",
                "controlled": True,
            },
        ],
    },
    "MRN-70402": {
        "patient": "David Moreno",
        "dob": "1972-12-03",
        "prescriptions": [
            {
                "rx_number": "RX-881004",
                "medication": "Lisinopril 10mg",
                "refills_remaining": 5,
                "status": "available",
                "pharmacy": "Maple Street Drugs — Oak Avenue",
                "controlled": False,
            },
            {
                "rx_number": "RX-881005",
                "medication": "Metformin 500mg",
                "refills_remaining": 2,
                "status": "available",
                "pharmacy": "Maple Street Drugs — Oak Avenue",
                "controlled": False,
            },
        ],
    },
}


def verify_patient(mrn, dob):
    patient = MOCK_PATIENTS.get(mrn)
    if patient and patient["dob"] == dob:
        return patient
    return None


def lookup_prescriptions(mrn):
    patient = MOCK_PATIENTS.get(mrn)
    if patient:
        return patient["prescriptions"]
    return []


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

agent = guava.Agent(
    name="Quinn",
    organization="CareRx Pharmacy",
    purpose=(
        "contact patients about prescription refills, verify their identity, "
        "look up their prescription status, and process refills or connect "
        "them with a pharmacist when needed"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
    "speak_to_pharmacist": "The caller wants to speak to a pharmacist or pharmacy staff",
})


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(
        contact_full_name=call.get_variable("patient_name"),
        voicemail_message=(
            f"Hi, this is Quinn from CareRx Pharmacy calling for "
            f"{call.get_variable('patient_name')}. We have an update for you. "
            f"Please call us back at 555-0180 at your convenience. Thank you."
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    patient_name = call.get_variable("patient_name")

    if outcome == "available":
        call.set_task(
            "verify_identity",
            objective=(
                f"Verify the identity of {patient_name} before accessing any "
                f"prescription information. Ask for their date of birth. Do not "
                f"share any medication names or prescription details until "
                f"identity is confirmed."
            ),
            checklist=[
                guava.Say(
                    "I'm calling about a prescription that may be due for a "
                    "refill. Before I can access your account, I need to verify "
                    "your identity."
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
                "contacted again and have been removed from the call list, and politely say goodbye."
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
                "records. For their privacy, you cannot access prescription "
                "information. Suggest they call the pharmacy directly at 555-0180, and politely say goodbye."
            )
        )
        return

    patient_name = call.get_variable("patient_name")
    prescriptions = lookup_prescriptions(mrn)

    if not prescriptions:
        call.hangup(
            final_instructions=(
                f"Let {patient_name} know there are no prescriptions on file "
                f"that need attention at this time. Thank them and wish them well, and politely say goodbye."
            )
        )
        return

    # Find the primary Rx to discuss (first one needing action, or first available)
    rx = prescriptions[0]
    call.set_variable("rx_number", rx["rx_number"])
    call.set_variable("medication", rx["medication"])
    call.set_variable("rx_status", rx["status"])
    call.set_variable("pharmacy_location", rx["pharmacy"])
    call.set_variable("is_controlled", rx["controlled"])

    call.add_info("prescription_details", {
        "rx_number": rx["rx_number"],
        "medication": rx["medication"],
        "refills_remaining": rx["refills_remaining"],
        "status": rx["status"],
        "pharmacy": rx["pharmacy"],
    })

    if rx["status"] == "available":
        call.set_task(
            "process_refill",
            objective=(
                f"Identity verified for {patient_name}. Their prescription for "
                f"{rx['medication']} (Rx #{rx['rx_number']}) has "
                f"{rx['refills_remaining']} refills remaining and is ready to "
                f"process. Confirm they would like to proceed and verify their "
                f"pharmacy is {rx['pharmacy']}. "
                f"Do NOT provide any dosage advice — your prescriber manages "
                f"dosage decisions."
            ),
            checklist=[
                guava.Say(
                    f"Thank you, {patient_name}. Your prescription for "
                    f"{rx['medication']} is due for a refill and you have "
                    f"{rx['refills_remaining']} refills remaining."
                ),
                guava.Field(
                    key="refill_confirmed",
                    description="Whether the patient would like to proceed with the refill",
                    field_type="multiple_choice",
                    choices=["yes", "no"],
                    required=True,
                ),
                guava.Field(
                    key="pharmacy_confirmed",
                    description=(
                        f"Confirm the patient's pharmacy is still {rx['pharmacy']}. "
                        f"If changed, collect the new pharmacy name and location."
                    ),
                    field_type="text",
                    required=True,
                ),
            ],
        )
    elif rx["status"] == "needs_renewal":
        call.set_task(
            "process_refill",
            objective=(
                f"Identity verified for {patient_name}. Their prescription for "
                f"{rx['medication']} (Rx #{rx['rx_number']}) has no refills "
                f"remaining and needs to be renewed by their prescriber. Explain "
                f"the situation and offer to transfer to the pharmacy for assistance. "
                f"Do NOT provide any dosage advice — your prescriber manages "
                f"dosage decisions."
            ),
            checklist=[
                guava.Say(
                    f"Thank you, {patient_name}. I'm calling about your "
                    f"prescription for {rx['medication']}. It looks like your "
                    f"refills have run out and the prescription needs to be "
                    f"renewed by your prescriber."
                ),
                guava.Field(
                    key="renewal_understood",
                    description="Whether the patient understands that a renewal is needed from their prescriber",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="wants_pharmacy_help",
                    description="Whether the patient wants to be connected with the pharmacy to assist with the renewal process",
                    field_type="multiple_choice",
                    choices=["yes", "no"],
                    required=True,
                ),
            ],
        )
    else:
        call.set_task(
            "process_refill",
            objective=(
                f"Identity verified for {patient_name}. Their prescription for "
                f"{rx['medication']} (Rx #{rx['rx_number']}) is a controlled "
                f"substance. Additional verification is required before a refill "
                f"can be processed. Explain that they will need to contact their "
                f"prescriber or visit the pharmacy in person. "
                f"Do NOT provide any dosage advice — your prescriber manages "
                f"dosage decisions."
            ),
            checklist=[
                guava.Say(
                    f"Thank you, {patient_name}. I'm calling about your "
                    f"prescription for {rx['medication']}. Because this is a "
                    f"controlled substance, there are additional steps needed "
                    f"to process a refill."
                ),
                guava.Field(
                    key="controlled_process_understood",
                    description=(
                        "Whether the patient understands the additional "
                        "verification steps required for controlled substance refills"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="prefers_contact_method",
                    description="Whether the patient prefers to contact their prescriber or visit the pharmacy in person",
                    field_type="multiple_choice",
                    choices=["contact_prescriber", "visit_pharmacy"],
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("process_refill")
def on_refill_processed(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    rx_status = call.get_variable("rx_status")

    if rx_status == "needs_renewal" and call.get_field("wants_pharmacy_help") == "yes":
        call.transfer(
            destination=PHARMACY_LINE,
            instructions=(
                f"Connect {patient_name} with the pharmacy team to assist with "
                f"the prescription renewal process. Let them know the pharmacist "
                f"can help coordinate with their prescriber."
            ),
        )
    elif rx_status == "available" and call.get_field("refill_confirmed") == "yes":
        pharmacy = call.get_field("pharmacy_confirmed")
        call.hangup(
            final_instructions=(
                f"Confirm to {patient_name} that their refill has been submitted "
                f"and will be ready for pickup at {pharmacy}. Let them know they "
                f"will receive a notification when it is ready. Thank them and "
                f"wish them well, and politely say goodbye."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {patient_name} for their time. Let them know they can "
                f"call CareRx Pharmacy at 555-0180 anytime for prescription "
                f"questions, and wish them well, and politely say goodbye."
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
            "again by phone, and wish them well, and politely say goodbye."
        )
    )


@agent.on_action("speak_to_pharmacist")
def handle_pharmacist_transfer(call: guava.Call) -> None:
    call.transfer(
        destination=PHARMACY_LINE,
        instructions=(
            "Let them know you are connecting them with a pharmacist now. "
            "Reassure them that their information has been saved."
        ),
    )


@agent.on_outbound_failed
def on_outbound_failed(event: OutboundCallFailed) -> None:
    logging.error("Outbound call failed: %s (code %d)", event.error_reason, event.error_code)


@agent.on_session_end
def on_session_end(call: guava.Call, event: BotSessionEnded) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "use_case": "prescription_refill",
        "patient_name": call.get_variable("patient_name"),
        "mrn": call.get_variable("mrn"),
        "rx_number": call.get_variable("rx_number"),
        "medication": call.get_variable("medication"),
        "rx_status": call.get_variable("rx_status"),
        "dob_verified": call.get_field("dob") is not None,
        "refill_confirmed": call.get_field("refill_confirmed"),
        "pharmacy_confirmed": call.get_field("pharmacy_confirmed"),
        "renewal_understood": call.get_field("renewal_understood"),
        "wants_pharmacy_help": call.get_field("wants_pharmacy_help"),
        "controlled_process_understood": call.get_field("controlled_process_understood"),
        "prefers_contact_method": call.get_field("prefers_contact_method"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound prescription refill call for CareRx Pharmacy"
    )
    parser.add_argument("phone", help="Patient phone number to call")
    parser.add_argument("--name", required=True, help="Full name of the patient")
    parser.add_argument(
        "--mrn",
        required=True,
        help="Medical record number (try MRN-70400, MRN-70401, or MRN-70402)",
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
