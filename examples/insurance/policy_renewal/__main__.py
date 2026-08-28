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


# ---------------------------------------------------------------------------
# Mock API — simulates a policy/renewal backend for demo purposes
# ---------------------------------------------------------------------------

MOCK_RENEWALS = {
    "KPC-449821": {
        "policyholder": "Maria Santos",
        "dob": "1985-03-14",
        "coverage_type": "auto",
        "current_premium": "$1,240.00",
        "renewal_premium": "$1,380.00",
        "premium_change": "+$140.00",
        "renewal_date": "2026-08-15",
        "agent_line": "+15551000600",
    },
    "KPC-338710": {
        "policyholder": "David Park",
        "dob": "1992-07-22",
        "coverage_type": "auto",
        "current_premium": "$980.00",
        "renewal_premium": "$980.00",
        "premium_change": "no change",
        "renewal_date": "2026-09-01",
        "agent_line": "+15551000601",
    },
    "KPC-112504": {
        "policyholder": "Rachel Kim",
        "dob": "1978-11-05",
        "coverage_type": "property",
        "current_premium": "$2,100.00",
        "renewal_premium": "$2,450.00",
        "premium_change": "+$350.00",
        "renewal_date": "2026-08-30",
        "agent_line": "+15551000602",
    },
}


def verify_policyholder(policy_number, dob):
    renewal = MOCK_RENEWALS.get(policy_number)
    if renewal and renewal["dob"] == dob:
        return renewal
    return None


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

agent = guava.Agent(
    name="Quinn",
    organization="Keystone Property & Casualty",
    purpose=(
        "reach out to policyholders ahead of their renewal date to present "
        "renewal terms, address questions about premium changes, and handle "
        "their renewal decision"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
    "speak_to_agent": "The caller wants to speak to an insurance agent or live representative",
})


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(
        contact_full_name=call.get_variable("contact_name"),
        voicemail_message=(
            f"Hi, this is Quinn from Keystone Property & Casualty calling for "
            f"{call.get_variable('contact_name')} regarding an upcoming policy "
            f"renewal. Please call us back at 1-800-555-0100 at your convenience. "
            f"Thank you."
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    contact_name = call.get_variable("contact_name")

    if outcome == "available":
        call.set_task(
            "verify_identity",
            objective=(
                f"Verify the identity of {contact_name} before sharing renewal "
                f"details. Ask for their date of birth. Do not discuss premium "
                f"amounts or renewal terms until identity is confirmed."
            ),
            checklist=[
                guava.Say(
                    f"I'm reaching out because your policy is coming up for renewal. "
                    f"Before I share the details, I need to verify your identity "
                    f"with a quick question."
                ),
                guava.Field(
                    key="dob",
                    description="The policyholder's date of birth for identity verification",
                    field_type="text",
                    required=True,
                ),
            ],
        )
    elif outcome == "do_not_contact":
        logging.info("Policyholder %s requested no further contact.", contact_name)
        call.hangup(
            final_instructions=(
                "Acknowledge their request. Let them know they will not be contacted "
                "again by phone and that renewal documents will be sent by mail, "
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
    policy_number = call.get_variable("policy_number")
    dob = call.get_field("dob")
    renewal = verify_policyholder(policy_number, dob)

    if renewal is None:
        logging.warning("Identity verification failed for policy %s.", policy_number)
        call.hangup(
            final_instructions=(
                "Let them know the date of birth provided does not match our records "
                "for this policy. For security, you cannot share renewal details. "
                "Suggest they call 1-800-555-0100 with their policy documents handy, "
                "and politely say goodbye."
            )
        )
        return

    contact_name = call.get_variable("contact_name")
    call.set_variable("agent_line", renewal["agent_line"])

    call.add_info("renewal_details", {
        "policy_number": policy_number,
        "coverage_type": renewal["coverage_type"],
        "current_premium": renewal["current_premium"],
        "renewal_premium": renewal["renewal_premium"],
        "premium_change": renewal["premium_change"],
        "renewal_date": renewal["renewal_date"],
    })

    call.set_task(
        "present_renewal",
        objective=(
            f"Identity verified. Present the renewal terms to {contact_name}. "
            f"Their {renewal['coverage_type']} policy ({policy_number}) renews on "
            f"{renewal['renewal_date']}. Current premium: {renewal['current_premium']}. "
            f"Renewal premium: {renewal['renewal_premium']} ({renewal['premium_change']}). "
            f"Ask whether they want to accept, negotiate, or decline. If the premium "
            f"increased, be prepared to address objections empathetically."
        ),
        checklist=[
            guava.Say(
                f"Thank you, {contact_name}. Your {renewal['coverage_type']} policy "
                f"{policy_number} is set to renew on {renewal['renewal_date']}. "
                f"Your current premium is {renewal['current_premium']} and the "
                f"renewal premium will be {renewal['renewal_premium']}."
            ),
            guava.Field(
                key="renewal_decision",
                description="The policyholder's decision on the renewal",
                field_type="multiple_choice",
                choices=["accept", "negotiate", "decline"],
                required=True,
            ),
            guava.Field(
                key="objection_details",
                description=(
                    "If the policyholder has concerns or objections about the premium "
                    "or coverage, record the details. Leave blank if none."
                ),
                field_type="text",
                required=False,
            ),
            guava.Field(
                key="coverage_changes_requested",
                description=(
                    "Any coverage changes the policyholder would like to make at "
                    "renewal, such as adjusting deductibles or adding coverage types"
                ),
                field_type="text",
                required=False,
            ),
        ],
    )


@agent.on_task_complete("present_renewal")
def on_renewal_presented(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    decision = call.get_field("renewal_decision")

    if decision == "accept":
        call.set_task(
            "confirm_renewal",
            objective=(
                f"{contact_name} has accepted the renewal. Confirm the billing "
                f"details and payment method for the renewal premium."
            ),
            checklist=[
                guava.Field(
                    key="payment_method",
                    description=(
                        "The policyholder's preferred payment method for the renewal "
                        "premium: autopay, check, credit card, or bank transfer"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="billing_frequency",
                    description=(
                        "The policyholder's preferred billing frequency: annual, "
                        "semi-annual, quarterly, or monthly"
                    ),
                    field_type="multiple_choice",
                    choices=["annual", "semi_annual", "quarterly", "monthly"],
                    required=True,
                ),
            ],
        )
    elif decision == "negotiate":
        agent_line = call.get_variable("agent_line")
        call.transfer(
            destination=agent_line,
            instructions=(
                f"Let {contact_name} know you're connecting them with a licensed "
                f"agent who can review their coverage options and discuss adjustments "
                f"to the premium. Reassure them that their information has been noted."
            ),
        )
    else:
        call.set_task(
            "retention_offer",
            objective=(
                f"{contact_name} has indicated they want to decline the renewal. "
                f"Before closing, offer a retention incentive: a free coverage review "
                f"with an agent to explore ways to reduce the premium while maintaining "
                f"adequate protection. Be respectful — do not pressure them."
            ),
            checklist=[
                guava.Field(
                    key="retention_accepted",
                    description=(
                        "Whether the policyholder accepted the offer to speak with "
                        "an agent for a coverage review before canceling"
                    ),
                    field_type="multiple_choice",
                    choices=["yes", "no"],
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("confirm_renewal")
def on_renewal_confirmed(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    call.hangup(
        final_instructions=(
            f"Thank {contact_name} for renewing. Confirm they will receive updated "
            f"policy documents by email and mail. Remind them they can call "
            f"1-800-555-0100 with any questions, and wish them well, and politely say goodbye."
        )
    )


@agent.on_task_complete("retention_offer")
def on_retention_handled(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    retention = call.get_field("retention_accepted")

    if retention == "yes":
        agent_line = call.get_variable("agent_line")
        call.transfer(
            destination=agent_line,
            instructions=(
                f"Let {contact_name} know you're connecting them with an agent "
                f"for a complimentary coverage review."
            ),
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {contact_name} for their time. Let them know the policy will "
                f"not renew and that they will receive confirmation by mail. Wish them "
                f"well and let them know Keystone is here if they ever need coverage "
                f"in the future, and politely say goodbye."
            )
        )


@agent.on_action_request
def on_action_request(call: guava.Call, intent_summary: str):
    return _mid_call_intent.classify(intent_summary)


@agent.on_action("do_not_contact")
def handle_dnc(call: guava.Call) -> None:
    logging.info("Policyholder %s requested DNC mid-call.", call.get_variable("contact_name"))
    call.hangup(
        final_instructions=(
            "Acknowledge their request. Let them know they will not be contacted "
            "again by phone and that renewal documents will be sent by mail, "
            "and politely say goodbye."
        )
    )


@agent.on_action("speak_to_agent")
def handle_transfer(call: guava.Call) -> None:
    agent_line = call.get_variable("agent_line")
    if agent_line:
        call.transfer(
            destination=agent_line,
            instructions="Let them know you're connecting them with an insurance agent now.",
        )
    else:
        call.hangup(
            final_instructions=(
                "Let them know an agent will call them back within one business day. "
                "Ask if there is a preferred time and thank them, and politely say goodbye."
            )
        )


@agent.on_outbound_failed
def on_outbound_failed(event: OutboundCallFailed) -> None:
    logging.error("Outbound call failed: %s (code %d)", event.error_reason, event.error_code)


@agent.on_session_end
def on_session_end(call: guava.Call, event: BotSessionEnded) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "use_case": "policy_renewal",
        "contact_name": call.get_variable("contact_name"),
        "policy_number": call.get_variable("policy_number"),
        "identity_verified": call.get_field("dob") is not None,
        "renewal_decision": call.get_field("renewal_decision"),
        "objection_details": call.get_field("objection_details"),
        "coverage_changes_requested": call.get_field("coverage_changes_requested"),
        "payment_method": call.get_field("payment_method"),
        "billing_frequency": call.get_field("billing_frequency"),
        "retention_accepted": call.get_field("retention_accepted"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound policy renewal call for Keystone Property & Casualty"
    )
    parser.add_argument("phone", help="Phone number to dial")
    parser.add_argument("--name", required=True, help="Full name of the policyholder")
    parser.add_argument(
        "--policy-number",
        required=True,
        help="Policy number (try KPC-449821, KPC-338710, or KPC-112504)",
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
            "policy_number": args.policy_number,
        },
    )
