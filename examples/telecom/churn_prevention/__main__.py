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
# Mock API — simulates a customer account and usage backend
# ---------------------------------------------------------------------------

MOCK_ACCOUNTS = {
    "NXM-440021": {
        "name": "David Park",
        "dob": "1992-07-22",
        "plan": "Essential 5GB",
        "monthly_cost": "$45",
        "tenure_months": 36,
        "usage": {
            "avg_data_gb": 4.8,
            "avg_minutes": 320,
            "avg_texts": 450,
            "overage_last_3mo": "$22.50",
        },
        "churn_risk": "high",
        "churn_signal": "price",
    },
    "NXM-550034": {
        "name": "Rachel Kim",
        "dob": "1978-11-05",
        "plan": "Premium Unlimited",
        "monthly_cost": "$85",
        "tenure_months": 18,
        "usage": {
            "avg_data_gb": 2.1,
            "avg_minutes": 120,
            "avg_texts": 80,
            "overage_last_3mo": "$0",
        },
        "churn_risk": "medium",
        "churn_signal": "switching_provider",
    },
    "NXM-660098": {
        "name": "Maria Santos",
        "dob": "1985-03-14",
        "plan": "Family Share 15GB",
        "monthly_cost": "$70",
        "tenure_months": 48,
        "usage": {
            "avg_data_gb": 14.2,
            "avg_minutes": 500,
            "avg_texts": 600,
            "overage_last_3mo": "$35.00",
        },
        "churn_risk": "high",
        "churn_signal": "service_quality",
    },
}


def verify_customer(account_number, dob):
    account = MOCK_ACCOUNTS.get(account_number)
    if account and account["dob"] == dob:
        return account
    return None


RETENTION_LINE = "+15551000400"


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

agent = guava.Agent(
    name="Quinn",
    organization="Nexus Mobile — Retention",
    purpose=(
        "speak with valued Nexus Mobile subscribers who may be considering "
        "leaving, understand their concerns, present personalized retention "
        "options, and connect them with a retention specialist when needed"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
    "speak_to_specialist": "The caller wants to speak to a retention specialist, manager, or live person",
})


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(
        contact_full_name=call.get_variable("customer_name"),
        voicemail_message=(
            f"Hi, this is Quinn from Nexus Mobile calling for "
            f"{call.get_variable('customer_name')}. We value your loyalty and "
            f"wanted to check in. No action needed — feel free to call us back "
            f"at your convenience. Thank you!"
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    customer_name = call.get_variable("customer_name")

    if outcome == "available":
        call.set_task(
            "verify_customer",
            objective=(
                f"Verify the identity of {customer_name} before discussing any "
                f"account details. Ask for their date of birth. Do not share "
                f"account or usage information until identity is confirmed."
            ),
            checklist=[
                guava.Say(
                    f"We truly value your loyalty and I'm reaching out because I'd "
                    f"like to make sure you're getting the most out of your Nexus "
                    f"Mobile service. Before we chat, I just need to verify your "
                    f"identity with a quick question."
                ),
                guava.Field(
                    key="dob",
                    description="The customer's date of birth for identity verification",
                    field_type="text",
                    required=True,
                ),
            ],
        )
    elif outcome == "do_not_contact":
        logging.info("Customer %s requested no further contact.", customer_name)
        call.hangup(
            final_instructions=(
                "Acknowledge their request. Let them know they will not be contacted "
                "again by phone, and politely say goodbye."
            )
        )
    elif outcome == "wrong_number":
        logging.info("Wrong number reached for %s.", customer_name)
        call.hangup(final_instructions="Apologize for the mistake and wish them well, and politely say goodbye.")
    else:
        logging.info("Could not reach %s (outcome: %s).", customer_name, outcome)
        call.hangup()


@agent.on_task_complete("verify_customer")
def on_customer_verified(call: guava.Call) -> None:
    account_number = call.get_variable("account_number")
    dob = call.get_field("dob")
    account = verify_customer(account_number, dob)

    if account is None:
        logging.warning("Identity verification failed for account %s.", account_number)
        call.hangup(
            final_instructions=(
                "Let them know the date of birth provided does not match our records. "
                "For security, you cannot discuss account details. Suggest they call "
                "Nexus Mobile customer service with their account documents handy, and politely say goodbye."
            )
        )
        return

    call.set_variable("plan", account["plan"])
    call.set_variable("monthly_cost", account["monthly_cost"])
    call.set_variable("churn_signal", account["churn_signal"])

    call.add_info("account_details", {
        "account_number": account_number,
        "plan": account["plan"],
        "monthly_cost": account["monthly_cost"],
        "tenure_months": account["tenure_months"],
        "churn_risk": account["churn_risk"],
        "churn_signal": account["churn_signal"],
    })

    call.add_info("usage_insights", {
        "avg_data_gb": account["usage"]["avg_data_gb"],
        "avg_minutes": account["usage"]["avg_minutes"],
        "avg_texts": account["usage"]["avg_texts"],
        "overage_last_3mo": account["usage"]["overage_last_3mo"],
    })

    call.set_task(
        "present_insights",
        objective=(
            f"Identity verified — speaking with {account['name']}. Present their "
            f"usage insights: they're on the {account['plan']} plan at "
            f"{account['monthly_cost']}/month, have been with Nexus Mobile for "
            f"{account['tenure_months']} months, and their recent usage shows "
            f"avg {account['usage']['avg_data_gb']}GB data, "
            f"{account['usage']['avg_minutes']} minutes, "
            f"{account['usage']['avg_texts']} texts. "
            f"Overages in the last 3 months: {account['usage']['overage_last_3mo']}. "
            f"Understand their satisfaction and any concerns."
        ),
        checklist=[
            guava.Say(
                f"Thank you, {account['name']}. Your identity has been verified. "
                f"I can see you've been a loyal Nexus Mobile customer for "
                f"{account['tenure_months']} months — we appreciate that. "
                f"Looking at your account, you're on the {account['plan']} plan. "
                f"I'd love to hear how things have been going for you."
            ),
            guava.Field(
                key="churn_reason",
                description=(
                    "The customer's primary reason for dissatisfaction or considering "
                    "leaving: price, service_quality, switching_provider, moving, or other"
                ),
                field_type="multiple_choice",
                choices=["price", "service_quality", "switching_provider", "moving", "other"],
                required=True,
            ),
        ],
    )


@agent.on_task_complete("present_insights")
def on_insights_presented(call: guava.Call) -> None:
    churn_reason = call.get_field("churn_reason")
    customer_name = call.get_variable("customer_name")
    plan = call.get_variable("plan")

    if churn_reason == "price":
        call.set_task(
            "retention_offer",
            objective=(
                f"{customer_name} is concerned about price on the {plan} plan. "
                f"Offer a $10/month loyalty discount for the next 12 months. "
                f"Make one offer — if they decline, respect the decision."
            ),
            checklist=[
                guava.Say(
                    f"I completely understand the importance of getting the best value. "
                    f"Given your loyalty, I can offer you a $10 per month discount on "
                    f"your current plan for the next 12 months."
                ),
                guava.Field(
                    key="offer_response",
                    description="The customer's response to the retention offer",
                    field_type="multiple_choice",
                    choices=["accepted_discount", "wants_plan_change", "declined", "needs_time"],
                    required=True,
                ),
            ],
        )
    elif churn_reason == "service_quality":
        call.set_task(
            "retention_offer",
            objective=(
                f"{customer_name} is unhappy with service quality. Apologize sincerely, "
                f"explain recent network improvements, and offer a one-time $25 bill "
                f"credit as a goodwill gesture. If the issue is complex, offer to "
                f"transfer to a specialist."
            ),
            checklist=[
                guava.Say(
                    f"I'm sorry to hear that your experience hasn't been up to our "
                    f"standards. We've been making significant network improvements "
                    f"in your area and I'd like to offer you a $25 bill credit as "
                    f"a thank-you for your patience."
                ),
                guava.Field(
                    key="offer_response",
                    description="The customer's response to the service quality resolution",
                    field_type="multiple_choice",
                    choices=["accepted_credit", "wants_specialist", "declined", "needs_time"],
                    required=True,
                ),
            ],
        )
    elif churn_reason == "switching_provider":
        call.set_task(
            "retention_offer",
            objective=(
                f"{customer_name} is considering another provider. Ask what the "
                f"competing offer includes so the retention team can follow up. "
                f"Do not promise to match any offer — simply collect the details."
            ),
            checklist=[
                guava.Field(
                    key="competitor_offer",
                    description="Details of the competing offer the customer has received",
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="offer_response",
                    description="Whether Nexus Mobile's counter-offer was accepted",
                    field_type="multiple_choice",
                    choices=["staying", "declined", "needs_time"],
                    required=True,
                ),
            ],
        )
    elif churn_reason == "moving":
        call.transfer(
            destination=RETENTION_LINE,
            instructions=(
                f"The customer ({customer_name}) is moving and needs to check "
                f"service availability in their new area. Connect them with a "
                f"retention specialist who can verify coverage and discuss options."
            ),
        )
        return
    else:
        call.set_task(
            "retention_offer",
            objective=(
                f"Understand {customer_name}'s specific concern and offer appropriate "
                f"help. If the situation is complex, offer to transfer to a specialist."
            ),
            checklist=[
                guava.Field(
                    key="offer_response",
                    description="The customer's response to assistance offered",
                    field_type="text",
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("retention_offer")
def on_retention_done(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    offer_response = call.get_field("offer_response")

    if offer_response in ("wants_specialist", "wants_plan_change"):
        call.transfer(
            destination=RETENTION_LINE,
            instructions=(
                f"Connect {customer_name} with a retention specialist. Their account "
                f"details and usage insights have been loaded into the call."
            ),
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {customer_name} sincerely for their time and loyalty. If they "
                f"accepted an offer, confirm the details and let them know a confirmation "
                f"will be sent. If they declined, express genuine understanding and let "
                f"them know Nexus Mobile's door is always open, and wish them well, and politely say goodbye."
            )
        )


@agent.on_action_request
def on_action_request(call: guava.Call, intent_summary: str):
    return _mid_call_intent.classify(intent_summary)


@agent.on_action("do_not_contact")
def handle_dnc(call: guava.Call) -> None:
    logging.info("Customer %s requested DNC mid-call.", call.get_variable("customer_name"))
    call.hangup(
        final_instructions=(
            "Acknowledge their request. Let them know they've been removed from the "
            "contact list and won't be called again, and wish them well, and politely say goodbye."
        )
    )


@agent.on_action("speak_to_specialist")
def handle_transfer_request(call: guava.Call) -> None:
    call.transfer(
        destination=RETENTION_LINE,
        instructions="Let them know you're connecting them with a retention specialist now.",
    )


@agent.on_outbound_failed
def on_outbound_failed(event: OutboundCallFailed) -> None:
    logging.error("Outbound call failed: %s (code %d)", event.error_reason, event.error_code)


@agent.on_session_end
def on_session_end(call: guava.Call, event: BotSessionEnded) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "use_case": "churn_prevention",
        "customer_name": call.get_variable("customer_name"),
        "account_number": call.get_variable("account_number"),
        "plan": call.get_variable("plan"),
        "churn_signal": call.get_variable("churn_signal"),
        "dob_verified": call.get_field("dob") is not None,
        "churn_reason": call.get_field("churn_reason"),
        "competitor_offer": call.get_field("competitor_offer"),
        "offer_response": call.get_field("offer_response"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound churn prevention call for Nexus Mobile"
    )
    parser.add_argument("phone", help="Customer phone number to call")
    parser.add_argument("--name", required=True, help="Customer full name")
    parser.add_argument(
        "--account-number",
        required=True,
        help="Account number (try NXM-440021, NXM-550034, or NXM-660098)",
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
            "customer_name": args.name,
            "account_number": args.account_number,
        },
    )
