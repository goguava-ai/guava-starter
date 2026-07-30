# SDK conformance: guava-sdk 0.35.0 (2026-07-21)
import argparse
import json
import logging
from datetime import datetime, time, timezone

import guava
from guava import logging_utils
from guava.helpers.llm import IntentRecognizer

BUSINESS_HOURS_START = time(8, 0)
BUSINESS_HOURS_END = time(18, 0)

ADJUSTER_LINE = "+15551000300"


# ---------------------------------------------------------------------------
# Mock API — simulates policy lookup and claim creation
# ---------------------------------------------------------------------------

MOCK_POLICIES = {
    "KPC-449821": {
        "policyholder": "Maria Santos",
        "dob": "1985-03-14",
        "coverage_types": ["auto", "property"],
        "status": "active",
    },
    "KPC-338710": {
        "policyholder": "David Park",
        "dob": "1992-07-22",
        "coverage_types": ["auto"],
        "status": "active",
    },
    "KPC-112504": {
        "policyholder": "Rachel Kim",
        "dob": "1978-11-05",
        "coverage_types": ["property", "liability"],
        "status": "lapsed",
    },
}


def lookup_policy(policy_number):
    return MOCK_POLICIES.get(policy_number)


def create_claim(policy_number, loss_type, details):
    claim_number = f"CLM-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}"
    logging.info("[MOCK API] POST /claims — created %s for policy %s", claim_number, policy_number)
    return claim_number


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

agent = guava.Agent(
    name="Avery",
    organization="Keystone Property & Casualty",
    purpose=(
        "assist policyholders with filing a First Notice of Loss and collecting "
        "the details needed to open a new insurance claim"
    ),
)

_mid_call_intent = IntentRecognizer({
    "speak_to_adjuster": "The caller wants to speak to a claims adjuster, live person, or supervisor",
    "withdraw": "The caller wants to stop the process, hang up, or call back later",
})


def _is_business_hours():
    now = datetime.now().time()
    return BUSINESS_HOURS_START <= now < BUSINESS_HOURS_END


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    if _is_business_hours():
        return guava.AcceptCall()
    return guava.DeclineCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "verify_policyholder",
        objective=(
            "Verify the caller's identity before collecting any claim information. "
            "Collect their policy number and date of birth. Do not discuss claim "
            "details, coverage, or policy status until identity is verified."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Keystone Property & Casualty. I'm sorry to "
                "hear you may be dealing with a loss. I'll help you get a claim started. "
                "First, I need to verify your identity."
            ),
            guava.Field(
                key="policy_number",
                description="The caller's policy number (format: KPC-NNNNNN)",
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="caller_dob",
                description="The caller's date of birth for identity verification",
                field_type="text",
                required=True,
            ),
        ],
    )


@agent.on_validate("policy_number")
def validate_policy_number(call: guava.Call, value) -> bool | tuple[bool, str]:
    if isinstance(value, str) and value.upper().startswith("KPC-") and len(value) >= 8:
        return True
    return (False, "That doesn't look like a valid policy number. It should start with KPC followed by a dash and six digits, like KPC-449821.")


@agent.on_task_complete("verify_policyholder")
def on_policyholder_verified(call: guava.Call) -> None:
    policy_number = call.get_field("policy_number")
    dob = call.get_field("caller_dob")
    policy = lookup_policy(policy_number)

    if policy is None or policy["dob"] != dob:
        logging.warning("Identity verification failed for policy %s.", policy_number)
        call.hangup(
            final_instructions=(
                "Let the caller know that the information provided does not match "
                "our records. For security, you cannot proceed. Suggest they double-check "
                "their policy number and try calling again, or visit the Keystone "
                "website for help locating their policy information, and politely say goodbye."
            )
        )
        return

    if policy["status"] == "lapsed":
        call.hangup(
            final_instructions=(
                "Let the caller know that their policy is no longer active. A claim "
                "cannot be filed against a lapsed policy. Suggest they contact their "
                "insurance agent to discuss reinstatement options, and politely say goodbye."
            )
        )
        return

    call.set_variable("policyholder_name", policy["policyholder"])
    call.set_variable("policy_number", policy_number)
    call.set_variable("coverage_types", policy["coverage_types"])

    call.add_info("verified_policy", {
        "policyholder": policy["policyholder"],
        "policy_number": policy_number,
        "coverage_types": policy["coverage_types"],
        "status": policy["status"],
    })

    call.set_task(
        "classify_loss",
        objective=(
            f"Identity verified — the caller is {policy['policyholder']}. "
            f"Now determine the type of loss they are reporting. Ask them to describe "
            f"what happened in general terms so we can categorize the claim correctly."
        ),
        checklist=[
            guava.Say(
                f"Thank you, {policy['policyholder']}. Your identity has been verified. "
                f"Now let's get your claim started. Can you tell me generally what happened?"
            ),
            guava.Field(
                key="loss_type",
                description="The category of loss being reported",
                field_type="multiple_choice",
                choices=["auto_collision", "auto_theft", "property_damage", "property_theft", "liability", "other"],
                required=True,
            ),
            guava.Field(
                key="injuries_involved",
                description="Whether any injuries to any person were involved in this incident",
                field_type="multiple_choice",
                choices=["yes", "no"],
                required=True,
            ),
        ],
    )


@agent.on_task_complete("classify_loss")
def on_loss_classified(call: guava.Call) -> None:
    loss_type = call.get_field("loss_type")
    injuries = call.get_field("injuries_involved")
    policyholder = call.get_variable("policyholder_name")

    call.set_variable("loss_type", loss_type)

    if injuries == "yes":
        call.transfer(
            destination=ADJUSTER_LINE,
            instructions=(
                f"The caller ({policyholder}) has reported injuries as part of this incident. "
                f"Let them know that because injuries are involved, you need to connect them "
                f"with a licensed adjuster who can guide them through the next steps. "
                f"Reassure them that their information so far has been saved."
            ),
        )
        return

    if loss_type in ("auto_collision", "auto_theft"):
        call.set_task(
            "collect_auto_details",
            objective=(
                f"Collect the details of the auto incident for {policyholder}. "
                f"Gather the date and location, a description of what happened, "
                f"the vehicles involved, and whether a police report was filed. "
                f"Be empathetic and patient."
            ),
            checklist=[
                guava.Field(
                    key="loss_date",
                    description="The date the incident occurred",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="loss_location",
                    description="The address or location where the incident occurred",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="loss_description",
                    description="A description of what happened",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="vehicles_involved",
                    description="The number of vehicles involved and their descriptions if known",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="police_report_filed",
                    description="Whether a police report was filed for this incident",
                    field_type="multiple_choice",
                    choices=["yes", "no", "not sure"],
                    required=True,
                ),
                guava.Field(
                    key="drivable",
                    description="Whether the insured vehicle is still drivable",
                    field_type="multiple_choice",
                    choices=["yes", "no"],
                    required=True,
                ),
            ],
        )
    elif loss_type in ("property_damage", "property_theft"):
        call.set_task(
            "collect_property_details",
            objective=(
                f"Collect the details of the property incident for {policyholder}. "
                f"Gather the date, property address, description of damage or theft, "
                f"and estimated value of the loss."
            ),
            checklist=[
                guava.Field(
                    key="loss_date",
                    description="The date the damage or theft occurred or was discovered",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="property_address",
                    description="The full address of the affected property",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="loss_description",
                    description="A description of the damage or what was stolen",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="estimated_value",
                    description="The caller's rough estimate of the total damage or loss value",
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="police_report_filed",
                    description="Whether a police report was filed",
                    field_type="multiple_choice",
                    choices=["yes", "no", "not sure"],
                    required=True,
                ),
                guava.Field(
                    key="property_secured",
                    description="Whether the property is currently secured and safe to occupy",
                    field_type="multiple_choice",
                    choices=["yes", "no", "not sure"],
                    required=True,
                ),
            ],
        )
    else:
        call.set_task(
            "collect_general_details",
            objective=(
                f"Collect the details of the incident for {policyholder}. "
                f"Gather the date, location, a thorough description of what happened, "
                f"and any other parties involved."
            ),
            checklist=[
                guava.Field(
                    key="loss_date",
                    description="The date the incident occurred",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="loss_location",
                    description="Where the incident occurred",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="loss_description",
                    description="A thorough description of what happened",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="other_parties",
                    description="Whether any other parties were involved and their details if known",
                    field_type="text",
                    required=False,
                ),
            ],
        )


def _finalize_claim(call: guava.Call) -> None:
    policy_number = call.get_variable("policy_number")
    loss_type = call.get_variable("loss_type")
    policyholder = call.get_variable("policyholder_name")

    details = {
        "loss_date": call.get_field("loss_date"),
        "loss_description": call.get_field("loss_description"),
        "loss_type": loss_type,
    }
    claim_number = create_claim(policy_number, loss_type, details)
    call.set_variable("claim_number", claim_number)

    call.hangup(
        final_instructions=(
            f"Let {policyholder} know that their claim has been filed successfully. "
            f"Their claim number is {claim_number}. A licensed adjuster will contact "
            f"them within one business day to discuss next steps. A confirmation email "
            f"will be sent to the address on file. Thank them for calling and let them "
            f"know Keystone is here to help, and politely say goodbye."
        )
    )


@agent.on_task_complete("collect_auto_details")
def on_auto_details(call: guava.Call) -> None:
    _finalize_claim(call)


@agent.on_task_complete("collect_property_details")
def on_property_details(call: guava.Call) -> None:
    _finalize_claim(call)


@agent.on_task_complete("collect_general_details")
def on_general_details(call: guava.Call) -> None:
    _finalize_claim(call)


@agent.on_question
def on_question(call: guava.Call, question: str) -> str:
    return (
        "I'm not able to make any determinations about coverage or claim outcomes. "
        "That will be handled by your assigned adjuster, who will review all the "
        "details of your case. For now, let's make sure we capture everything you "
        "need to report."
    )


@agent.on_action_request
def on_action_request(call: guava.Call, intent_summary: str):
    return _mid_call_intent.classify(intent_summary)


@agent.on_action("speak_to_adjuster")
def handle_transfer(call: guava.Call) -> None:
    call.transfer(
        destination=ADJUSTER_LINE,
        instructions=(
            "Let the caller know you're connecting them with a claims representative "
            "now. Let them know that any information collected so far has been saved."
        ),
    )


@agent.on_action("withdraw")
def handle_withdraw(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            "Let them know that's completely fine. No claim has been filed yet. "
            "They can call back anytime during business hours to start the process "
            "again, and wish them well, and politely say goodbye."
        )
    )


@agent.on_session_end
def on_session_end(call: guava.Call, event: guava.BotSessionEnded) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "use_case": "first_notice_of_loss",
        "policyholder_name": call.get_variable("policyholder_name"),
        "policy_number": call.get_variable("policy_number"),
        "loss_type": call.get_variable("loss_type"),
        "claim_number": call.get_variable("claim_number"),
        "loss_date": call.get_field("loss_date"),
        "loss_description": call.get_field("loss_description"),
        "injuries_involved": call.get_field("injuries_involved"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()

    parser = argparse.ArgumentParser(
        description="Inbound First Notice of Loss agent for Keystone Property & Casualty"
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
    group.add_argument(
        "--call", metavar="PHONE_NUMBER", help="Place an outbound call for testing."
    )
    parser.add_argument(
        "--from-number", metavar="FROM_NUMBER", help="Caller ID for --call mode."
    )
    args = parser.parse_args()

    if args.call:
        agent.call_phone(args.from_number or "", args.call)
    elif args.phone is not None:
        agent.listen_phone(args.phone)
    elif args.webrtc is not None:
        agent.listen_webrtc(args.webrtc or None)
    elif args.sip:
        agent.listen_sip(args.sip)
    else:
        agent.call_local()
