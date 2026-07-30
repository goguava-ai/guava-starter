# SDK conformance: guava-sdk 0.35.0 (2026-07-21)
import argparse
import json
import logging
import os
from datetime import datetime, timezone

import guava
from guava import logging_utils
from guava.helpers.llm import IntentRecognizer

agent = guava.Agent(
    name="Skyler",
    organization="SwiftShip Logistics - Customs & Compliance",
    purpose=(
        "contact shippers or brokers to verify customs documentation status, "
        "collect missing information required for clearance, and address common "
        "customs questions"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
    "speak_to_compliance": "The caller wants to speak to a compliance specialist or live person",
})


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(
        contact_full_name=call.get_variable("contact_name"),
        voicemail_message=(
            f"Hi, this is Skyler from SwiftShip Logistics Customs and Compliance "
            f"calling for {call.get_variable('contact_name')} regarding shipment "
            f"number {call.get_variable('shipment_number')}. This shipment is "
            f"currently on hold pending documentation. Please call us back at your "
            f"earliest convenience to avoid further clearance delays. Thank you."
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    contact_name = call.get_variable("contact_name")
    shipment_number = call.get_variable("shipment_number")
    missing_docs = call.get_variable("missing_docs")

    if outcome == "available":
        call.set_task(
            "check_doc_status",
            objective=(
                f"Connect with {contact_name} regarding shipment number "
                f"{shipment_number}. The following documentation is currently "
                f"missing or incomplete: {missing_docs}. Determine the overall "
                f"document status before proceeding."
            ),
            checklist=[
                guava.Say(
                    f"I'm calling about shipment number {shipment_number}. We have "
                    f"a hold on this shipment pending the following documentation: "
                    f"{missing_docs}."
                ),
                guava.Field(
                    key="document_status",
                    description=(
                        "The overall status of the required customs documents for this shipment"
                    ),
                    field_type="multiple_choice",
                    choices=["complete", "missing_items", "questions"],
                    required=True,
                ),
            ],
        )
    elif outcome == "do_not_contact":
        logging.info("Contact %s requested no further contact.", contact_name)
        call.hangup(
            final_instructions=(
                "Acknowledge their request. Let them know they will not be contacted "
                "again by phone and that any future compliance notices will be sent by "
                "email, and politely say goodbye."
            )
        )
    elif outcome == "wrong_number":
        logging.info("Wrong number reached for %s.", contact_name)
        call.hangup(final_instructions="Apologize for the mistake and wish them well, and politely say goodbye.")
    else:
        logging.info("Could not reach %s (outcome: %s).", contact_name, outcome)
        call.hangup()


@agent.on_task_complete("check_doc_status")
def on_doc_status_done(call: guava.Call) -> None:
    status = call.get_field("document_status")
    contact_name = call.get_variable("contact_name")
    shipment_number = call.get_variable("shipment_number")

    if status == "complete":
        call.hangup(
            final_instructions=(
                f"Confirm with {contact_name} that all required customs documents "
                f"for shipment {shipment_number} are in order. Let them know the "
                f"compliance team will process clearance and they can expect the "
                f"shipment to move forward within 1 to 2 business days. Thank them "
                f"for their prompt attention, and politely say goodbye."
            )
        )
    elif status == "missing_items":
        call.set_task(
            "collect_missing_docs",
            objective=(
                f"{contact_name} indicates documents are still missing for shipment "
                f"{shipment_number}. Collect details on which specific documents can "
                f"be provided, when they will be submitted, and note any items they "
                f"need help locating."
            ),
            checklist=[
                guava.Field(
                    key="documents_to_provide",
                    description=(
                        "Which of the missing documents the contact can provide "
                        "(commercial invoice, certificate of origin, packing list, etc.)"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="submission_deadline",
                    description="When the contact expects to submit the missing documents",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="needs_assistance",
                    description=(
                        "Whether the contact needs help locating or preparing any of "
                        "the required documents"
                    ),
                    field_type="multiple_choice",
                    choices=["yes", "no"],
                    required=True,
                ),
            ],
        )
    else:
        call.set_task(
            "address_customs_questions",
            objective=(
                f"{contact_name} has questions about customs requirements for shipment "
                f"{shipment_number}. Collect their specific questions — they may be "
                f"about tariff codes, country of origin, declared values, dangerous "
                f"goods, or something else. Your job is to document the questions "
                f"clearly so a compliance specialist can follow up with accurate "
                f"answers. Do not attempt to answer customs questions yourself."
            ),
            checklist=[
                guava.Field(
                    key="customs_questions",
                    description="The specific customs questions the contact has",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="needs_specialist_followup",
                    description=(
                        "Whether the contact's questions require follow-up from a "
                        "compliance specialist"
                    ),
                    field_type="multiple_choice",
                    choices=["yes", "no"],
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("collect_missing_docs")
def on_missing_docs_done(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    call.hangup(
        final_instructions=(
            f"Thank {contact_name} for confirming the documentation plan. Remind "
            f"them that clearance cannot proceed until all required documents are "
            f"submitted. If they need assistance, let them know the compliance team "
            f"will reach out, and wish them a good day, and politely say goodbye."
        )
    )


@agent.on_task_complete("address_customs_questions")
def on_questions_done(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    needs_followup = call.get_field("needs_specialist_followup")

    if needs_followup == "yes":
        call.hangup(
            final_instructions=(
                f"Let {contact_name} know that a compliance specialist will follow up "
                f"within one business day to address their remaining questions. Thank "
                f"them for their patience, and politely say goodbye."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {contact_name} for their questions. Remind them to submit any "
                f"outstanding documents as soon as possible to avoid further delays. "
                f"Wish them a good day, and politely say goodbye."
            )
        )


@agent.on_action_request
def on_action_request(call: guava.Call, intent_summary: str):
    return _mid_call_intent.classify(intent_summary)


@agent.on_action("do_not_contact")
def handle_dnc(call: guava.Call) -> None:
    logging.info("Contact %s requested DNC mid-call.", call.get_variable("contact_name"))
    call.hangup(
        final_instructions=(
            "Acknowledge their request. Let them know they've been removed from the "
            "call list and future compliance notices will be sent by email, and politely say goodbye."
        )
    )


@agent.on_action("speak_to_compliance")
def handle_speak_to_compliance(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            "Let them know that a compliance specialist will call them back within "
            "one business day. Ask if there is a preferred time and thank them, and politely say goodbye."
        )
    )


@agent.on_outbound_failed
def on_outbound_failed(event: guava.OutboundCallFailed) -> None:
    logging.error("Outbound call failed: %s (code %d)", event.error_reason, event.error_code)


@agent.on_session_end
def on_session_end(call: guava.Call, event: guava.BotSessionEnded) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "contact_name": call.get_variable("contact_name"),
        "shipment_number": call.get_variable("shipment_number"),
        "missing_docs": call.get_variable("missing_docs"),
        "document_status": call.get_field("document_status"),
        "documents_to_provide": call.get_field("documents_to_provide"),
        "submission_deadline": call.get_field("submission_deadline"),
        "needs_assistance": call.get_field("needs_assistance"),
        "customs_questions": call.get_field("customs_questions"),
        "needs_specialist_followup": call.get_field("needs_specialist_followup"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound customs compliance call for SwiftShip Logistics"
    )
    parser.add_argument("phone", help="Shipper or broker phone number to call")
    parser.add_argument("--name", required=True, help="Full name of the shipper or broker contact")
    parser.add_argument("--shipment-number", required=True, help="Shipment or freight number")
    parser.add_argument(
        "--missing-docs",
        required=True,
        help="Description of the documentation that is missing or incomplete",
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
            "shipment_number": args.shipment_number,
            "missing_docs": args.missing_docs,
        },
    )
