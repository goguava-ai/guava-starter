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
    name="Blake",
    organization="Keystone Property & Casualty — Underwriting",
    purpose=(
        "collect supplemental property and risk information required to complete "
        "the underwriting review for a new policy application"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
    "speak_to_someone": "The caller wants to speak to an underwriter or live person",
})


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(
        contact_full_name=call.get_variable("contact_name"),
        voicemail_message=(
            f"Hi, this is Blake from the Underwriting department at Keystone "
            f"Property & Casualty calling for {call.get_variable('contact_name')}. "
            f"We need a few additional details to complete your policy application. "
            f"Please call us back at 1-800-555-0100 at your convenience. Thank you."
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    contact_name = call.get_variable("contact_name")
    application_number = call.get_variable("application_number")

    if outcome == "available":
        call.set_task(
            "underwriting_collection",
            objective=(
                f"Collect supplemental property details from {contact_name} for "
                f"application {application_number}. Gather information about the "
                f"property year built, roof history, security systems, prior claims, "
                f"and liability features. Be professional and explain that this "
                f"ensures accurate and fair coverage."
            ),
            checklist=[
                guava.Say(
                    f"I'm reaching out about your policy application "
                    f"{application_number}. Our team needs a few additional details "
                    f"about the property before we can finalize your coverage. This "
                    f"should only take a few minutes."
                ),
                guava.Field(
                    key="property_year_built",
                    description="The year the property was originally built",
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="roof_last_replaced",
                    description=(
                        "The year or approximate timeframe when the roof was last "
                        "replaced or significantly repaired"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="security_system",
                    description=(
                        "Whether a monitored security or burglar alarm system is "
                        "installed, and the monitoring provider if known"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="prior_claims_count",
                    description=(
                        "The number of insurance claims filed against any property "
                        "or auto policy within the last five years"
                    ),
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="trampoline_or_pool",
                    description=(
                        "Whether the property has a trampoline, swimming pool, hot "
                        "tub, or other recreational features that may affect liability"
                    ),
                    field_type="text",
                    required=True,
                ),
            ],
        )
    elif outcome == "do_not_contact":
        logging.info("Applicant %s requested no further contact.", contact_name)
        call.hangup(
            final_instructions=(
                "Acknowledge their request. Let them know they will not be contacted "
                "again by phone and that underwriting correspondence will be sent by "
                "mail, and politely say goodbye."
            )
        )
    elif outcome == "wrong_number":
        logging.info("Wrong number for %s.", contact_name)
        call.hangup(final_instructions="Apologize for the mistake and wish them well, and politely say goodbye.")
    else:
        logging.info("Could not reach %s (outcome: %s).", contact_name, outcome)
        call.hangup()


@agent.on_task_complete("underwriting_collection")
def on_collection_done(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    prior_claims = call.get_field("prior_claims_count")
    trampoline_or_pool = call.get_field("trampoline_or_pool")

    has_disclosures = (
        (prior_claims is not None and prior_claims > 0)
        or (trampoline_or_pool and trampoline_or_pool.lower() not in ("no", "none", "n/a"))
    )

    if has_disclosures:
        call.set_task(
            "disclosure_followup",
            objective=(
                f"{contact_name} reported prior claims or liability features that "
                f"require additional detail. Collect specifics to complete the "
                f"underwriting file."
            ),
            checklist=[
                guava.Field(
                    key="prior_claim_details",
                    description=(
                        "A brief description of prior claims if any were reported, "
                        "including type and approximate settlement"
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="liability_details",
                    description=(
                        "Details about liability features reported (e.g., pool has "
                        "a fence and lock, trampoline has a safety net)"
                    ),
                    field_type="text",
                    required=False,
                ),
            ],
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {contact_name} for their time. Let them know the underwriting "
                f"team will review the application and they can expect to hear back "
                f"within 2 to 3 business days, and wish them a great day, and politely say goodbye."
            )
        )


@agent.on_task_complete("disclosure_followup")
def on_disclosure_done(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    call.hangup(
        final_instructions=(
            f"Thank {contact_name} for providing that additional information. "
            f"Let them know the underwriting team will complete their review and "
            f"they can expect to hear back within 2 to 3 business days. Wish them "
            f"a great day, and politely say goodbye."
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
            "the contact list and will not be called again, and wish them well, "
            "and politely say goodbye."
        )
    )


@agent.on_action("speak_to_someone")
def handle_speak_to_someone(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            "Let them know someone from the Underwriting team will call them back "
            "within one business day. Ask if there's a preferred time and thank them, "
            "and politely say goodbye."
        )
    )


@agent.on_outbound_failed
def on_outbound_failed(event: OutboundCallFailed) -> None:
    logging.error("Outbound call failed: %s (code %d)", event.error_reason, event.error_code)


@agent.on_session_end
def on_session_end(call: guava.Call, event: BotSessionEnded) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "use_case": "underwriting_collection",
        "contact_name": call.get_variable("contact_name"),
        "application_number": call.get_variable("application_number"),
        "property_year_built": call.get_field("property_year_built"),
        "roof_last_replaced": call.get_field("roof_last_replaced"),
        "security_system": call.get_field("security_system"),
        "prior_claims_count": call.get_field("prior_claims_count"),
        "trampoline_or_pool": call.get_field("trampoline_or_pool"),
        "prior_claim_details": call.get_field("prior_claim_details"),
        "liability_details": call.get_field("liability_details"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound underwriting data collection for Keystone Property & Casualty"
    )
    parser.add_argument("phone", help="Phone number to dial")
    parser.add_argument("--name", required=True, help="Full name of the applicant")
    parser.add_argument(
        "--application-number", required=True, help="Policy application number"
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
            "application_number": args.application_number,
        },
    )
