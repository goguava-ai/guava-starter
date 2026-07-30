# SDK conformance: guava-sdk 0.35.0 (2026-07-21)
import argparse
import json
import logging
import os
from datetime import datetime, timezone

import guava
from guava import logging_utils
from guava.helpers.llm import IntentRecognizer


# ---------------------------------------------------------------------------
# Mock API — simulates a claims backend for demo purposes
# ---------------------------------------------------------------------------

MOCK_CLAIMS = {
    "CLM-20261201": {
        "policyholder": "Maria Santos",
        "dob": "1985-03-14",
        "policy_number": "KPC-449821",
        "loss_type": "auto",
        "status": "approved",
        "status_detail": (
            "The claim has been approved. A settlement check for $4,200 will be "
            "mailed to the address on file within 5 to 7 business days."
        ),
        "adjuster": "Claims Adjuster Line",
        "adjuster_number": "+15551000200",
    },
    "CLM-20261415": {
        "policyholder": "David Park",
        "dob": "1992-07-22",
        "policy_number": "KPC-338710",
        "loss_type": "property",
        "status": "pending",
        "status_detail": (
            "The claim is currently under review. We are waiting on the inspection "
            "report from the field adjuster, which is expected within 3 business days."
        ),
        "adjuster": "Property Claims Team",
        "adjuster_number": "+15551000201",
    },
    "CLM-20260987": {
        "policyholder": "Rachel Kim",
        "dob": "1978-11-05",
        "policy_number": "KPC-112504",
        "loss_type": "auto",
        "status": "denied",
        "status_detail": (
            "The claim was denied because the incident occurred outside the policy "
            "coverage period. The policyholder has the right to file an appeal within "
            "60 days of the denial notice."
        ),
        "adjuster": "Appeals Department",
        "adjuster_number": "+15551000202",
    },
}


def verify_identity(claim_number, dob):
    claim = MOCK_CLAIMS.get(claim_number)
    if claim and claim["dob"] == dob:
        return claim
    return None


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

agent = guava.Agent(
    name="Morgan",
    organization="Keystone Property & Casualty — Claims",
    purpose=(
        "provide claimants with a proactive status update on their open claim, "
        "answer questions about next steps, and connect them with an adjuster "
        "when needed"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
    "speak_to_adjuster": "The caller wants to speak to a claims adjuster or live person about their claim",
})


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(
        contact_full_name=call.get_variable("contact_name"),
        voicemail_message=(
            f"Hi, this is Morgan from Keystone Property & Casualty calling for "
            f"{call.get_variable('contact_name')} regarding an open claim. "
            f"Please call us back at 1-800-555-0100 at your convenience. Thank you."
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    contact_name = call.get_variable("contact_name")

    if outcome == "available":
        call.set_task(
            "verify_identity",
            objective=(
                f"Verify the identity of {contact_name} before sharing any claim "
                f"details. Ask for their date of birth. Do not share any claim status "
                f"or policy information until identity is confirmed."
            ),
            checklist=[
                guava.Say(
                    f"I have an update on your claim. Before I share any details, "
                    f"I need to verify your identity with a quick question."
                ),
                guava.Field(
                    key="dob",
                    description="The claimant's date of birth for identity verification",
                    field_type="text",
                    required=True,
                ),
            ],
        )
    elif outcome == "do_not_contact":
        logging.info("Claimant %s requested no further contact.", contact_name)
        call.hangup(
            final_instructions=(
                "Acknowledge their request. Let them know they will not be contacted "
                "again by phone, and that any future updates will be sent by mail, "
                "and politely say goodbye."
            )
        )
    elif outcome == "wrong_number":
        logging.info("Wrong number for %s.", contact_name)
        call.hangup(final_instructions="Apologize for the mistake and wish them well, and politely say goodbye.")
    else:
        logging.info("Could not reach %s (outcome: %s).", contact_name, outcome)
        call.hangup()


@agent.on_task_complete("verify_identity")
def on_identity_verified(call: guava.Call) -> None:
    claim_number = call.get_variable("claim_number")
    dob = call.get_field("dob")
    claim = verify_identity(claim_number, dob)

    if claim is None:
        logging.warning("Identity verification failed for claim %s.", claim_number)
        call.hangup(
            final_instructions=(
                "Let them know the date of birth provided does not match our records "
                "for this claim. For security, you cannot share claim details. "
                "Suggest they call the main claims line at 1-800-555-0100 with their "
                "policy documents handy, and politely say goodbye."
            )
        )
        return

    call.set_variable("claim_status", claim["status"])
    call.set_variable("adjuster_number", claim["adjuster_number"])

    call.add_info("claim_details", {
        "claim_number": claim_number,
        "status": claim["status"],
        "status_detail": claim["status_detail"],
        "adjuster": claim["adjuster"],
    })

    if claim["status"] == "denied":
        call.set_task(
            "deliver_status",
            objective=(
                f"Deliver the claim status update to {call.get_variable('contact_name')}. "
                f"The claim has been denied. Explain the reason clearly and empathetically. "
                f"Let them know they have the right to appeal within 60 days. "
                f"Offer to transfer them to the Appeals Department if they would like "
                f"to discuss their options. "
                f"Do NOT speculate about the outcome of an appeal or whether the denial "
                f"might be overturned. Only share what is in the claim details provided."
            ),
            checklist=[
                guava.Field(
                    key="status_understood",
                    description="Whether the claimant understood the status and reason for denial",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="wants_to_appeal",
                    description="Whether the claimant wants to file an appeal or speak with the Appeals Department",
                    field_type="multiple_choice",
                    choices=["yes", "no", "needs time to decide"],
                    required=True,
                ),
            ],
        )
    elif claim["status"] == "pending":
        call.set_task(
            "deliver_status",
            objective=(
                f"Deliver the claim status update to {call.get_variable('contact_name')}. "
                f"The claim is pending. Explain what is being waited on and the expected "
                f"timeline. Ask if they have any additional documentation to submit. "
                f"Do NOT predict when the claim will be resolved or estimate a payout amount."
            ),
            checklist=[
                guava.Field(
                    key="status_understood",
                    description="Whether the claimant understood the current status and next steps",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="has_additional_docs",
                    description="Whether the claimant has additional documentation, photos, or estimates to submit",
                    field_type="multiple_choice",
                    choices=["yes", "no"],
                    required=True,
                ),
            ],
        )
    else:
        call.set_task(
            "deliver_status",
            objective=(
                f"Deliver the claim status update to {call.get_variable('contact_name')}. "
                f"The claim has been approved. Share the settlement details and timeline. "
                f"Ask if they have a preferred repair vendor. "
                f"Do NOT modify the settlement amount or make promises beyond what is stated."
            ),
            checklist=[
                guava.Field(
                    key="status_understood",
                    description="Whether the claimant understood the settlement details and timeline",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="repair_vendor_preference",
                    description="Whether the claimant has a preferred repair contractor or vendor",
                    field_type="text",
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("deliver_status")
def on_status_delivered(call: guava.Call) -> None:
    claim_status = call.get_variable("claim_status")

    if claim_status == "denied" and call.get_field("wants_to_appeal") == "yes":
        adjuster_number = call.get_variable("adjuster_number")
        call.transfer(
            destination=adjuster_number,
            instructions=(
                "Let the claimant know you're transferring them to the Appeals "
                "Department now, and wish them the best with their appeal."
            ),
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {call.get_variable('contact_name')} for their time. "
                f"Remind them they can call the main claims line at 1-800-555-0100 "
                f"if they have any additional questions, and wish them well, and politely say goodbye."
            )
        )


@agent.on_action_request
def on_action_request(call: guava.Call, intent_summary: str):
    return _mid_call_intent.classify(intent_summary)


@agent.on_action("do_not_contact")
def handle_dnc(call: guava.Call) -> None:
    logging.info("Claimant %s requested DNC mid-call.", call.get_variable("contact_name"))
    call.hangup(
        final_instructions=(
            "Acknowledge their request. Let them know they will not be contacted "
            "again by phone and that future claim updates will be sent by mail, "
            "and politely say goodbye."
        )
    )


@agent.on_action("speak_to_adjuster")
def handle_transfer_request(call: guava.Call) -> None:
    adjuster_number = call.get_variable("adjuster_number")
    if adjuster_number:
        call.transfer(
            destination=adjuster_number,
            instructions="Let them know you're connecting them with a claims representative now.",
        )
    else:
        call.hangup(
            final_instructions=(
                "Let them know a claims adjuster will call them back within one "
                "business day. Ask if there is a preferred time and thank them, "
                "and politely say goodbye."
            )
        )


@agent.on_outbound_failed
def on_outbound_failed(event: guava.OutboundCallFailed) -> None:
    logging.error("Outbound call failed: %s (code %d)", event.error_reason, event.error_code)


@agent.on_session_end
def on_session_end(call: guava.Call, event: guava.BotSessionEnded) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "use_case": "claims_status_update",
        "contact_name": call.get_variable("contact_name"),
        "claim_number": call.get_variable("claim_number"),
        "claim_status": call.get_variable("claim_status"),
        "dob_verified": call.get_field("dob") is not None,
        "status_understood": call.get_field("status_understood"),
        "wants_to_appeal": call.get_field("wants_to_appeal"),
        "has_additional_docs": call.get_field("has_additional_docs"),
        "repair_vendor_preference": call.get_field("repair_vendor_preference"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound claims status update call for Keystone Property & Casualty"
    )
    parser.add_argument("phone", help="Phone number to dial")
    parser.add_argument("--name", required=True, help="Full name of the claimant")
    parser.add_argument(
        "--claim-number",
        required=True,
        help="Claim number (try CLM-20261201, CLM-20261415, or CLM-20260987)",
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
            "contact_name": args.name,
            "claim_number": args.claim_number,
        },
    )
