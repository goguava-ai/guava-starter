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

agent = guava.Agent(
    name="Taylor",
    organization="National Internet Bank",
    purpose=(
        "follow up on a pending loan application, inform the applicant of the "
        "current status, and collect any outstanding documentation or next steps"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
    "speak_to_someone": "The caller wants to speak to a loan officer or live person",
})


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(
        contact_full_name=call.get_variable("contact_name"),
        voicemail_message=(
            f"Hi, this is Taylor from National Internet Bank calling for "
            f"{call.get_variable('contact_name')}. We're reaching out regarding "
            f"your loan application. Please call us back at 1-800-555-0180 at "
            f"your convenience. Thank you."
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    contact_name = call.get_variable("contact_name")
    loan_type = call.get_variable("loan_type")
    loan_status = call.get_variable("loan_status")

    if outcome == "available":
        call.set_task(
            "followup",
            objective=(
                f"Follow up with {contact_name} regarding their {loan_type} "
                f"application at National Internet Bank. The application status is: "
                f"{loan_status}. Deliver the status update, address any questions, "
                f"and collect next steps based on the status."
            ),
            checklist=[
                guava.Say(
                    f"I'm calling regarding your {loan_type} application — I have "
                    f"an update for you."
                ),
                guava.Field(
                    key="status_understood",
                    description=(
                        "Confirmation that the applicant understood the status update"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="additional_questions",
                    description=(
                        "Any questions or concerns the applicant raised about their "
                        "application, eligibility, interest rates, or timeline"
                    ),
                    field_type="text",
                    required=False,
                ),
            ],
        )
    elif outcome == "do_not_contact":
        logging.info("Applicant %s requested no further contact.", contact_name)
        call.hangup(
            final_instructions=(
                "Acknowledge their request. Let them know they will not be contacted "
                "again by phone. Note that application updates will be available "
                "through online banking or by calling the main line, and politely say goodbye."
            )
        )
    elif outcome == "wrong_number":
        logging.info("Wrong number for %s.", contact_name)
        call.hangup(final_instructions="Apologize for the mistake and wish them well, and politely say goodbye.")
    else:
        logging.info("Could not reach %s (outcome: %s).", contact_name, outcome)
        call.hangup()


@agent.on_task_complete("followup")
def on_followup_done(call: guava.Call) -> None:
    loan_status = call.get_variable("loan_status")
    contact_name = call.get_variable("contact_name")

    if loan_status == "approved":
        call.set_task(
            "approved_next_steps",
            objective=(
                f"{contact_name}'s loan has been approved. Collect their signing "
                f"preference — in person or electronic — and confirm they have "
                f"the required documents ready: government-issued ID, proof of "
                f"income, and proof of address. A confirmation email will follow "
                f"with the full document checklist and funding timeline details."
            ),
            checklist=[
                guava.Say(
                    f"Congratulations, {contact_name}! Your loan has been approved. "
                    f"Let me walk you through what happens next."
                ),
                guava.Field(
                    key="signing_preference",
                    description=(
                        "Whether the applicant prefers to sign the loan agreement "
                        "in person at a branch or via electronic signature"
                    ),
                    field_type="multiple_choice",
                    choices=["in_person", "electronic"],
                    required=True,
                ),
                guava.Field(
                    key="documents_ready",
                    description=(
                        "Whether the applicant has the required documents ready: "
                        "government-issued ID, proof of income, and proof of address"
                    ),
                    field_type="multiple_choice",
                    choices=["yes", "need_time"],
                    required=True,
                ),
            ],
        )
    elif loan_status == "pending":
        call.set_task(
            "pending_followup",
            objective=(
                f"{contact_name}'s loan is still pending review. Explain the expected "
                f"timeline and ask if they have any missing documents to submit."
            ),
            checklist=[
                guava.Say(
                    f"Your application is currently under review. Our team typically "
                    f"completes the review within 3 to 5 business days."
                ),
                guava.Field(
                    key="has_missing_docs",
                    description=(
                        "Whether the applicant has any additional documentation "
                        "they need to submit"
                    ),
                    field_type="multiple_choice",
                    choices=["yes", "no", "not_sure"],
                    required=True,
                ),
                guava.Field(
                    key="submission_method",
                    description=(
                        "If the applicant has documents to submit, their preferred "
                        "method: email, fax, or in person at a branch"
                    ),
                    field_type="multiple_choice",
                    choices=["email", "fax", "branch"],
                    required=False,
                ),
            ],
        )
    else:
        call.set_task(
            "denied_alternatives",
            objective=(
                f"{contact_name}'s loan application was denied. Empathetically explain "
                f"the decision and present alternative options: applying for a different "
                f"loan product, reapplying with a co-signer, or speaking with a loan "
                f"officer about other paths forward."
            ),
            checklist=[
                guava.Say(
                    f"I understand this isn't the news you were hoping for. While your "
                    f"application wasn't approved at this time, I'd like to share some "
                    f"alternative options that may be available to you."
                ),
                guava.Field(
                    key="alternative_interest",
                    description=(
                        "Which alternative option interests the applicant: a different "
                        "loan product, reapplying with a co-signer, or speaking with "
                        "a loan officer for other options"
                    ),
                    field_type="multiple_choice",
                    choices=["different_product", "cosigner", "speak_to_officer", "none"],
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("approved_next_steps")
def on_approved_done(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    call.hangup(
        final_instructions=(
            f"Thank {contact_name} and confirm the next steps based on their signing "
            f"preference. Let them know they'll receive a confirmation email with the "
            f"full document checklist, and wish them well, and politely say goodbye."
        )
    )


@agent.on_task_complete("pending_followup")
def on_pending_done(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    call.hangup(
        final_instructions=(
            f"Thank {contact_name} for their patience. Let them know a loan officer "
            f"will reach out once the review is complete, typically within 3 to 5 "
            f"business days, and wish them a great day, and politely say goodbye."
        )
    )


@agent.on_task_complete("denied_alternatives")
def on_denied_done(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    call.hangup(
        final_instructions=(
            f"Thank {contact_name} for their time. If they expressed interest in an "
            f"alternative, confirm that a loan officer will follow up. Remind them "
            f"they can call 1-800-555-0180 anytime, and wish them well, and politely say goodbye."
        )
    )


@agent.on_action_request
def on_action_request(call: guava.Call, intent_summary: str):
    return _mid_call_intent.classify(intent_summary)


@agent.on_action("do_not_contact")
def handle_dnc(call: guava.Call) -> None:
    logging.info("Applicant %s requested DNC mid-call.", call.get_variable("contact_name"))
    call.hangup(
        final_instructions=(
            "Acknowledge their request. Let them know they have been removed from "
            "the contact list and will not be called again, and wish them well, and politely say goodbye."
        )
    )


@agent.on_action("speak_to_someone")
def handle_speak_to_someone(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            "Let them know a loan officer will call them back within one business "
            "day. Ask if there's a preferred time and thank them for their patience, and politely say goodbye."
        )
    )


@agent.on_outbound_failed
def on_outbound_failed(event: OutboundCallFailed) -> None:
    logging.error("Outbound call failed: %s (code %d)", event.error_reason, event.error_code)


@agent.on_session_end
def on_session_end(call: guava.Call, event: BotSessionEnded) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "use_case": "loan_followup",
        "contact_name": call.get_variable("contact_name"),
        "loan_type": call.get_variable("loan_type"),
        "loan_status": call.get_variable("loan_status"),
        "status_understood": call.get_field("status_understood"),
        "additional_questions": call.get_field("additional_questions"),
        "signing_preference": call.get_field("signing_preference"),
        "documents_ready": call.get_field("documents_ready"),
        "has_missing_docs": call.get_field("has_missing_docs"),
        "submission_method": call.get_field("submission_method"),
        "alternative_interest": call.get_field("alternative_interest"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound loan follow-up call for National Internet Bank"
    )
    parser.add_argument("phone", help="Phone number to dial")
    parser.add_argument("--name", required=True, help="Full name of the loan applicant")
    parser.add_argument(
        "--loan-type",
        default="personal loan",
        help="Type of loan (default: 'personal loan')",
    )
    parser.add_argument(
        "--loan-status",
        default="pending",
        help="Loan status: approved, pending, or denied (default: 'pending')",
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
            "loan_type": args.loan_type,
            "loan_status": args.loan_status,
        },
    )
