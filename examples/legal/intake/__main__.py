# SDK conformance: guava-sdk 0.44.0 (2026-09-15)
import argparse
import json
import logging
from datetime import datetime, timezone

import guava
from guava import logging_utils
from guava.helpers.llm import IntentRecognizer
from guava.events import BotSessionEnded, OutboundCallFailed

ATTORNEY_LINE = "+15551000700"


# ---------------------------------------------------------------------------
# Mock API — simulates a conflict check for demo purposes
# ---------------------------------------------------------------------------

MOCK_CONFLICTS = {
    "johnson": "CONFLICT — Hargrove & Associates currently represents an adverse party named Johnson in matter HAR-2025-0412.",
}


def check_conflicts(adverse_party_names):
    if not adverse_party_names:
        return None
    for name in adverse_party_names.lower().split(","):
        name = name.strip()
        for key, conflict in MOCK_CONFLICTS.items():
            if key in name:
                return conflict
    return None


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

agent = guava.Agent(
    name="Devon",
    organization="Hargrove & Associates Law Firm",
    purpose=(
        "conduct an initial client intake, classify the type of legal matter, "
        "collect case-specific information, and determine whether a conflict "
        "of interest exists before connecting the caller with an attorney"
    ),
)

_mid_call_intent = IntentRecognizer({
    "speak_to_attorney": "The caller wants to speak to an attorney or lawyer immediately",
    "withdraw": "The caller wants to stop the process, hang up, or call back later",
})

_case_type_classifier = IntentRecognizer({
    "family": "The matter involves divorce, custody, child support, adoption, or other family law issues",
    "criminal": "The matter involves criminal charges, arrest, DUI, or defense against prosecution",
    "civil": "The matter involves a civil dispute, contract issue, property matter, or personal injury",
    "immigration": "The matter involves visas, citizenship, deportation, asylum, or immigration status",
    "other": "The matter does not clearly fit into family, criminal, civil, or immigration categories",
})


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "initial_intake",
        objective=(
            "Collect the prospective client's contact information and a general "
            "description of their legal matter. This information is needed to "
            "classify the case type and perform a conflict check. Do NOT provide "
            "any legal advice or opinions — you can help collect information but "
            "cannot provide legal guidance."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Hargrove & Associates. My name is Devon and "
                "I'll be collecting some initial information about your matter today. "
                "I want to let you know upfront that I can help collect information, "
                "but I can't provide legal guidance. An attorney will review your "
                "information and reach out to you directly."
            ),
            guava.Field(
                key="caller_name",
                description="The caller's full legal name",
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="caller_phone",
                description="The best phone number to reach the caller",
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="caller_email",
                description="The caller's email address for follow-up correspondence",
                field_type="text",
                required=False,
            ),
            guava.Field(
                key="brief_description",
                description=(
                    "A concise description of the legal matter in the caller's own "
                    "words — what happened and what they need help with"
                ),
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="adverse_parties",
                description=(
                    "The full names of any opposing or adverse parties involved in "
                    "the matter, needed for conflict of interest check"
                ),
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="urgency_level",
                description="The urgency of the matter",
                field_type="multiple_choice",
                choices=["urgent", "standard", "exploratory"],
                required=True,
            ),
        ],
    )


@agent.on_task_complete("initial_intake")
def on_initial_intake_done(call: guava.Call) -> None:
    adverse_parties = call.get_field("adverse_parties")
    conflict = check_conflicts(adverse_parties)
    urgency = call.get_field("urgency_level")

    if conflict:
        logging.warning("Conflict detected: %s", conflict)
        call.hangup(
            final_instructions=(
                "Let the caller know that unfortunately, after running a preliminary "
                "check, there may be a conflict of interest that prevents the firm "
                "from taking their case. Suggest they consult with another firm. "
                "Do NOT disclose the nature of the conflict or which party is involved. "
                "Wish them well, and politely say goodbye."
            )
        )
        return

    if urgency == "urgent":
        call.transfer(
            destination=ATTORNEY_LINE,
            instructions=(
                "The caller has indicated an urgent legal matter. Let them know "
                "you're connecting them with an attorney right away. Reassure them "
                "that the information collected so far has been saved."
            ),
        )
        return

    description = call.get_field("brief_description") or ""
    case_type = _case_type_classifier.classify(description)
    call.set_variable("case_type", case_type)

    call.add_info("intake_summary", {
        "caller_name": call.get_field("caller_name"),
        "case_type": case_type,
        "brief_description": description,
        "urgency": urgency,
    })

    if case_type == "family":
        call.set_task(
            "collect_case_details",
            objective=(
                "Collect family law-specific details. Ask about the type of family "
                "matter (divorce, custody, adoption, etc.), whether children are "
                "involved, and whether any court filings have already been made. "
                "Do NOT provide legal guidance."
            ),
            checklist=[
                guava.Field(
                    key="family_matter_type",
                    description="The specific type of family law matter",
                    field_type="multiple_choice",
                    choices=["divorce", "custody", "child_support", "adoption", "other"],
                    required=True,
                ),
                guava.Field(
                    key="children_involved",
                    description="Whether minor children are involved in the matter",
                    field_type="multiple_choice",
                    choices=["yes", "no"],
                    required=True,
                ),
                guava.Field(
                    key="existing_court_filings",
                    description="Whether any court filings have already been made",
                    field_type="multiple_choice",
                    choices=["yes", "no", "not_sure"],
                    required=True,
                ),
            ],
        )
    elif case_type == "criminal":
        call.set_task(
            "collect_case_details",
            objective=(
                "Collect criminal defense-specific details. Ask about the nature "
                "of the charges, whether an arrest has been made, and the court "
                "date if known. Do NOT provide legal guidance."
            ),
            checklist=[
                guava.Field(
                    key="charge_description",
                    description="A description of the criminal charges or allegations",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="arrest_made",
                    description="Whether the caller has been arrested or charged",
                    field_type="multiple_choice",
                    choices=["yes", "no"],
                    required=True,
                ),
                guava.Field(
                    key="court_date",
                    description="The next scheduled court date, if known",
                    field_type="text",
                    required=False,
                ),
            ],
        )
    elif case_type == "civil":
        call.set_task(
            "collect_case_details",
            objective=(
                "Collect civil matter details. Ask about the type of dispute, "
                "approximate amount involved, and whether any legal action has "
                "been initiated. Do NOT provide legal guidance."
            ),
            checklist=[
                guava.Field(
                    key="dispute_type",
                    description="The type of civil dispute (contract, property, personal injury, etc.)",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="amount_involved",
                    description="The approximate dollar amount involved in the dispute",
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="legal_action_initiated",
                    description="Whether any legal action (lawsuit, demand letter) has been initiated",
                    field_type="multiple_choice",
                    choices=["yes", "no", "not_sure"],
                    required=True,
                ),
            ],
        )
    elif case_type == "immigration":
        call.set_task(
            "collect_case_details",
            objective=(
                "Collect immigration-specific details. Ask about the type of "
                "immigration matter, current status, and any deadlines. "
                "Do NOT provide legal guidance."
            ),
            checklist=[
                guava.Field(
                    key="immigration_matter_type",
                    description="The type of immigration matter (visa, citizenship, asylum, deportation, etc.)",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="current_status",
                    description="The caller's current immigration status if they are comfortable sharing",
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="deadline",
                    description="Any upcoming deadlines related to the immigration matter",
                    field_type="text",
                    required=False,
                ),
            ],
        )
    else:
        call.set_task(
            "collect_case_details",
            objective=(
                "Collect general details about the legal matter since it doesn't "
                "fit a standard category. Ask for a more detailed description and "
                "any relevant dates. Do NOT provide legal guidance."
            ),
            checklist=[
                guava.Field(
                    key="detailed_description",
                    description="A more detailed description of the legal matter and circumstances",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="relevant_dates",
                    description="Any important dates related to the matter (deadlines, incidents, etc.)",
                    field_type="text",
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("collect_case_details")
def on_case_details_done(call: guava.Call) -> None:
    caller_name = call.get_field("caller_name")

    call.set_task(
        "schedule_consultation",
        objective=(
            f"The intake is complete. Schedule a consultation for {caller_name}. "
            f"Ask for their preferred day and time for an attorney callback."
        ),
        checklist=[
            guava.Field(
                key="preferred_consultation_time",
                description="The caller's preferred day and time for an attorney consultation",
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="how_heard_about_us",
                description="How the caller heard about or was referred to Hargrove & Associates",
                field_type="text",
                required=False,
            ),
        ],
    )


@agent.on_task_complete("schedule_consultation")
def on_consultation_scheduled(call: guava.Call) -> None:
    caller_name = call.get_field("caller_name")
    call.hangup(
        final_instructions=(
            f"Thank {caller_name} for their time. Confirm that their information "
            f"has been received and that an attorney will review the details and "
            f"call them back at the number provided, at or near their preferred "
            f"time. Remind them that nothing discussed during this call constitutes "
            f"legal advice, and wish them well, and politely say goodbye."
        )
    )


@agent.on_question
def on_question(call: guava.Call, question: str) -> str:
    return (
        "I appreciate you asking, but I'm not able to provide legal advice or "
        "guidance. That will be handled by your assigned attorney, who will "
        "review all the details of your situation. For now, let's make sure "
        "we capture everything you need to share."
    )


@agent.on_action_request
def on_action_request(call: guava.Call, intent_summary: str):
    return _mid_call_intent.classify(intent_summary)


@agent.on_action("speak_to_attorney")
def handle_transfer(call: guava.Call) -> None:
    call.transfer(
        destination=ATTORNEY_LINE,
        instructions=(
            "Let the caller know you're connecting them with an attorney now. "
            "Reassure them that the information collected so far has been saved."
        ),
    )


@agent.on_action("withdraw")
def handle_withdraw(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            "Let them know that's completely fine. No formal intake has been "
            "submitted yet. They can call back anytime to start the process again. "
            "Wish them well, and politely say goodbye."
        )
    )


@agent.on_session_end
def on_session_end(call: guava.Call, event: BotSessionEnded) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "use_case": "legal_intake",
        "caller_name": call.get_field("caller_name"),
        "caller_phone": call.get_field("caller_phone"),
        "caller_email": call.get_field("caller_email"),
        "case_type": call.get_variable("case_type"),
        "brief_description": call.get_field("brief_description"),
        "adverse_parties": call.get_field("adverse_parties"),
        "urgency_level": call.get_field("urgency_level"),
        "family_matter_type": call.get_field("family_matter_type"),
        "charge_description": call.get_field("charge_description"),
        "dispute_type": call.get_field("dispute_type"),
        "immigration_matter_type": call.get_field("immigration_matter_type"),
        "preferred_consultation_time": call.get_field("preferred_consultation_time"),
        "how_heard_about_us": call.get_field("how_heard_about_us"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()

    parser = argparse.ArgumentParser(
        description="Inbound legal intake agent for Hargrove & Associates"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--phone", metavar="PHONE_NUMBER", nargs="?", const="", help="Listen for phone calls."
    )
    group.add_argument(
        "--webrtc", metavar="WEBRTC_CODE", nargs="?", const="", help="Listen on a WebRTC code."
    )
    group.add_argument("--local", action="store_true", help="Start a local call.")
    group.add_argument("--sip", metavar="SIP_CODE", help="Listen on a SIP code 'guavasip-...'.")
    args = parser.parse_args()

    if args.phone is not None:
        agent.listen_phone(args.phone)
    elif args.webrtc is not None:
        agent.listen_webrtc(args.webrtc or None)
    elif args.sip:
        agent.listen_sip(args.sip)
    else:
        agent.call_local()
