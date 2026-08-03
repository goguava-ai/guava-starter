# SDK conformance: guava-sdk 0.35.0 (2026-07-21)
import argparse
import json
import logging
from datetime import datetime, timezone

import guava
from guava import logging_utils
from guava.helpers.llm import IntentRecognizer
from guava.events import BotSessionEnded, OutboundCallFailed

FINANCE_TEAM_LINE = "+15551000400"

CREDIT_RANGES = {
    "800_plus": {"label": "800+", "tier": "excellent"},
    "740_799": {"label": "740-799", "tier": "good"},
    "670_739": {"label": "670-739", "tier": "fair"},
    "580_669": {"label": "580-669", "tier": "below_average"},
    "below_580": {"label": "Below 580", "tier": "poor"},
}

EMPLOYMENT_QUALIFIED = {"full_time", "self_employed", "retired"}


def evaluate_qualification(credit_range, employment_status, annual_income, down_payment):
    credit_info = CREDIT_RANGES.get(credit_range, {})
    tier = credit_info.get("tier", "unknown")

    if tier in ("excellent", "good") and employment_status in EMPLOYMENT_QUALIFIED:
        return "pre_qualified"
    elif tier == "poor" or employment_status == "unemployed":
        return "declined"
    else:
        return "needs_review"


agent = guava.Agent(
    name="Noel",
    organization="Lakeside Auto Group — Finance",
    purpose=(
        "collect income and credit background information from prospective buyers "
        "over the phone so the finance team can prepare pre-qualification options "
        "before their dealership visit"
    ),
)

_mid_call_intent = IntentRecognizer({
    "rate_question": "The caller is asking about interest rates, APR, monthly payments, or specific financing terms",
    "speak_to_finance": "The caller wants to speak to a finance manager or live person",
})


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "verify_intent",
        objective=(
            "Welcome the caller to the Lakeside Auto Group Finance pre-qualification "
            "line. Confirm they are calling to get pre-qualified for vehicle financing "
            "and collect their name and the vehicle they are interested in."
        ),
        checklist=[
            guava.Say(
                "Welcome to the Lakeside Auto Group Finance pre-qualification line. "
                "I can help you get started so our finance team has everything ready "
                "before your visit. It should only take a few minutes."
            ),
            guava.Field(
                key="full_name",
                description="The caller's full legal name",
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="vehicle_of_interest",
                description="The make, model, and year of the vehicle the caller is interested in",
                field_type="text",
                required=True,
            ),
        ],
    )


@agent.on_task_complete("verify_intent")
def on_intent_verified(call: guava.Call) -> None:
    full_name = call.get_field("full_name")
    vehicle = call.get_field("vehicle_of_interest")

    call.set_variable("full_name", full_name)
    call.set_variable("vehicle_of_interest", vehicle)

    call.set_task(
        "collect_financials",
        objective=(
            f"Collect the financial details needed to pre-qualify {full_name} for "
            f"financing on a {vehicle}. Be conversational and reassuring — let them "
            f"know this information is kept confidential and is only used to prepare "
            f"financing options. Do NOT quote specific interest rates, monthly payments, "
            f"or financing terms — those will come from the finance team."
        ),
        checklist=[
            guava.Field(
                key="annual_income",
                description="The caller's total annual income before taxes",
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="employment_status",
                description="The caller's current employment status",
                field_type="multiple_choice",
                choices=["full_time", "part_time", "self_employed", "retired", "unemployed"],
                required=True,
            ),
            guava.Field(
                key="down_payment_amount",
                description="The amount the caller plans to put down as a down payment",
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="credit_score_range",
                description="The caller's estimated credit score range",
                field_type="multiple_choice",
                choices=["800_plus", "740_799", "670_739", "580_669", "below_580"],
                required=True,
            ),
            guava.Field(
                key="trade_in_vehicle",
                description=(
                    "Details about any vehicle the caller intends to trade in, "
                    "including year, make, model, and approximate mileage"
                ),
                field_type="text",
                required=False,
            ),
        ],
    )


@agent.on_task_complete("collect_financials")
def on_financials_collected(call: guava.Call) -> None:
    full_name = call.get_variable("full_name")
    credit_range = call.get_field("credit_score_range")
    employment = call.get_field("employment_status")
    income = call.get_field("annual_income")
    down_payment = call.get_field("down_payment_amount")

    result = evaluate_qualification(credit_range, employment, income, down_payment)
    call.set_variable("qualification_result", result)

    call.add_info("qualification_summary", {
        "result": result,
        "credit_range": credit_range,
        "employment_status": employment,
        "annual_income": income,
        "down_payment": down_payment,
    })

    if result == "pre_qualified":
        call.set_task(
            "deliver_result",
            objective=(
                f"{full_name} is pre-qualified based on their credit and income profile. "
                f"Let them know the great news — they are pre-qualified for financing "
                f"and a finance specialist will have personalized options ready for their "
                f"visit. Ask if they would like to be connected to the finance team now "
                f"or prefer to discuss options at the dealership. "
                f"Do NOT quote specific rates or monthly payment amounts."
            ),
            checklist=[
                guava.Field(
                    key="connect_to_finance",
                    description="Whether the caller wants to be connected to a finance specialist now",
                    field_type="multiple_choice",
                    choices=["yes", "no"],
                    required=True,
                ),
            ],
        )
    elif result == "declined":
        call.hangup(
            final_instructions=(
                f"Let {full_name} know that based on the information provided, "
                f"the standard pre-qualification criteria were not met at this time. "
                f"However, Lakeside Auto Group works with a wide range of lending "
                f"partners and there may still be options available. Encourage them to "
                f"visit the dealership where a finance specialist can explore all "
                f"possibilities in person. Be empathetic and encouraging, and politely say goodbye."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Let {full_name} know that their application needs a closer review "
                f"by the finance team. A finance specialist will call them back within "
                f"one business day with personalized options. Assure them this is normal "
                f"and does not mean anything negative, and thank them for their time, and politely say goodbye."
            )
        )


@agent.on_task_complete("deliver_result")
def on_result_delivered(call: guava.Call) -> None:
    full_name = call.get_variable("full_name")

    if call.get_field("connect_to_finance") == "yes":
        call.transfer(
            destination=FINANCE_TEAM_LINE,
            instructions=(
                f"Let {full_name} know you're connecting them with a finance specialist "
                f"now. Let them know all the information collected has been saved so they "
                f"won't need to repeat anything."
            ),
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {full_name} for taking the time to get pre-qualified. Let them "
                f"know that a finance specialist will have their personalized options "
                f"ready when they visit the dealership, and wish them a great day, and politely say goodbye."
            )
        )


@agent.on_action_request
def on_action_request(call: guava.Call, intent_summary: str):
    return _mid_call_intent.classify(intent_summary)


@agent.on_action("rate_question")
def handle_rate_question(call: guava.Call) -> None:
    pass


@agent.on_question
def on_question(call: guava.Call, question: str) -> str:
    return (
        "I'm not able to quote specific interest rates or monthly payment amounts — "
        "those depend on the full application review by our finance team. Once we "
        "finish collecting your information, a finance specialist will be able to "
        "provide personalized numbers."
    )


@agent.on_action("speak_to_finance")
def handle_transfer(call: guava.Call) -> None:
    call.transfer(
        destination=FINANCE_TEAM_LINE,
        instructions=(
            "Let the caller know you're connecting them with a finance specialist now. "
            "Any information collected so far has been saved."
        ),
    )


@agent.on_session_end
def on_session_end(call: guava.Call, event: BotSessionEnded) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "use_case": "financing_prequalification",
        "full_name": call.get_variable("full_name"),
        "vehicle_of_interest": call.get_variable("vehicle_of_interest"),
        "qualification_result": call.get_variable("qualification_result"),
        "annual_income": call.get_field("annual_income"),
        "employment_status": call.get_field("employment_status"),
        "down_payment_amount": call.get_field("down_payment_amount"),
        "credit_score_range": call.get_field("credit_score_range"),
        "trade_in_vehicle": call.get_field("trade_in_vehicle"),
        "connect_to_finance": call.get_field("connect_to_finance"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()

    parser = argparse.ArgumentParser(
        description="Inbound financing pre-qualification agent for Lakeside Auto Group"
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
