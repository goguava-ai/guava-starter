# SDK conformance: guava-sdk 0.38.0 (2026-08-11)
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
# Mock API — simulates account, plan, and usage lookup
# ---------------------------------------------------------------------------

MOCK_ACCOUNTS = {
    "NXM-770011": {
        "name": "Aisha Johnson",
        "dob": "1990-06-18",
        "plan": "Basic 3GB",
        "monthly_cost": "$35",
        "usage": {
            "avg_data_gb": 8.5,
            "avg_minutes": 400,
            "avg_texts": 350,
            "overage_last_3mo": "$45.00",
        },
        "usage_pattern": "high_data",
    },
    "NXM-770022": {
        "name": "Thomas Chen",
        "dob": "1987-02-10",
        "plan": "Premium Unlimited",
        "monthly_cost": "$85",
        "usage": {
            "avg_data_gb": 1.8,
            "avg_minutes": 90,
            "avg_texts": 50,
            "overage_last_3mo": "$0",
        },
        "usage_pattern": "low_usage",
    },
    "NXM-770033": {
        "name": "Sofia Reyes",
        "dob": "1995-09-30",
        "plan": "Essential 5GB",
        "monthly_cost": "$45",
        "usage": {
            "avg_data_gb": 4.2,
            "avg_minutes": 600,
            "avg_texts": 200,
            "overage_last_3mo": "$0",
            "international_minutes": 85,
        },
        "usage_pattern": "international",
    },
}


def verify_customer(account_number, dob):
    account = MOCK_ACCOUNTS.get(account_number)
    if account and account["dob"] == dob:
        return account
    return None


SALES_LINE = "+15551000500"


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

agent = guava.Agent(
    name="Reese",
    organization="Nexus Mobile",
    purpose=(
        "review customers' current plan and usage patterns, recommend a plan "
        "that better fits their needs — whether that means upgrading, "
        "downgrading, or adding an international feature — and assist with "
        "the change"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
    "speak_to_sales": "The caller wants to speak to a sales representative, account specialist, or live person",
})


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(
        contact_full_name=call.get_variable("customer_name"),
        voicemail_message=(
            f"Hi, this is Reese from Nexus Mobile calling for "
            f"{call.get_variable('customer_name')}. We've been looking at your "
            f"plan and have some options that might save you money or better fit "
            f"your needs. No action needed — call us back at your convenience. "
            f"Thank you!"
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
                f"account or plan details. Ask for their date of birth."
            ),
            checklist=[
                guava.Say(
                    f"I'm reaching out because we've been reviewing your plan "
                    f"and I think there might be an option that better fits your "
                    f"needs. Before I share any details, I just need to verify "
                    f"your identity quickly."
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
                "Nexus Mobile customer service, and politely say goodbye."
            )
        )
        return

    call.set_variable("plan", account["plan"])
    call.set_variable("monthly_cost", account["monthly_cost"])
    call.set_variable("usage_pattern", account["usage_pattern"])

    call.add_info("plan_and_usage", {
        "account_number": account_number,
        "current_plan": account["plan"],
        "monthly_cost": account["monthly_cost"],
        "avg_data_gb": account["usage"]["avg_data_gb"],
        "avg_minutes": account["usage"]["avg_minutes"],
        "avg_texts": account["usage"]["avg_texts"],
        "overage_last_3mo": account["usage"]["overage_last_3mo"],
        "usage_pattern": account["usage_pattern"],
    })

    usage_pattern = account["usage_pattern"]

    if usage_pattern == "high_data":
        call.set_task(
            "recommend_plan",
            objective=(
                f"Identity verified — speaking with {account['name']}. They are on "
                f"the {account['plan']} plan at {account['monthly_cost']}/month but "
                f"averaging {account['usage']['avg_data_gb']}GB of data — well above "
                f"their plan's limit. They've incurred "
                f"{account['usage']['overage_last_3mo']} in overages over the last 3 "
                f"months. Recommend the Unlimited plan at $65/month — it would "
                f"eliminate overages and likely save them money."
            ),
            checklist=[
                guava.Say(
                    f"Thank you, {account['name']}. Looking at your account, you're "
                    f"currently on the {account['plan']} plan at "
                    f"{account['monthly_cost']} per month. I can see you've been "
                    f"averaging {account['usage']['avg_data_gb']}GB of data, which "
                    f"has resulted in {account['usage']['overage_last_3mo']} in "
                    f"overages recently. Our Unlimited plan at $65 per month would "
                    f"eliminate those overages entirely."
                ),
                guava.Field(
                    key="upgrade_decision",
                    description="The customer's decision on the recommended plan change",
                    field_type="multiple_choice",
                    choices=["upgrade_now", "think_about_it", "declined"],
                    required=True,
                ),
            ],
        )
    elif usage_pattern == "low_usage":
        call.set_task(
            "recommend_plan",
            objective=(
                f"Identity verified — speaking with {account['name']}. They are on "
                f"the {account['plan']} plan at {account['monthly_cost']}/month but "
                f"only averaging {account['usage']['avg_data_gb']}GB of data and "
                f"{account['usage']['avg_minutes']} minutes. Recommend the Essential "
                f"5GB plan at $45/month — it covers their usage and saves $40/month. "
                f"Yes, this is a downgrade recommendation — it's the right thing to do."
            ),
            checklist=[
                guava.Say(
                    f"Thank you, {account['name']}. Looking at your account, you're "
                    f"on the {account['plan']} plan at {account['monthly_cost']} per "
                    f"month. Based on your usage — averaging just "
                    f"{account['usage']['avg_data_gb']}GB of data and "
                    f"{account['usage']['avg_minutes']} minutes — you could save "
                    f"$40 per month by switching to our Essential 5GB plan at $45, "
                    f"which would still cover everything you need."
                ),
                guava.Field(
                    key="upgrade_decision",
                    description="The customer's decision on the recommended plan change",
                    field_type="multiple_choice",
                    choices=["switch_now", "think_about_it", "keep_current"],
                    required=True,
                ),
            ],
        )
    else:
        intl_minutes = account["usage"].get("international_minutes", 0)
        call.set_task(
            "recommend_plan",
            objective=(
                f"Identity verified — speaking with {account['name']}. They are on "
                f"the {account['plan']} plan and averaging {intl_minutes} "
                f"international minutes per month. Recommend the International "
                f"add-on at $15/month which includes 200 international minutes "
                f"and reduced per-minute rates."
            ),
            checklist=[
                guava.Say(
                    f"Thank you, {account['name']}. Looking at your account, I "
                    f"noticed you're making about {intl_minutes} international "
                    f"minutes of calls per month. Our International add-on is just "
                    f"$15 per month and includes 200 international minutes with "
                    f"significantly reduced rates beyond that."
                ),
                guava.Field(
                    key="upgrade_decision",
                    description="The customer's decision on the international add-on",
                    field_type="multiple_choice",
                    choices=["add_now", "think_about_it", "not_interested"],
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("recommend_plan")
def on_recommendation_done(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    decision = call.get_field("upgrade_decision")

    if decision in ("upgrade_now", "switch_now", "add_now"):
        call.transfer(
            destination=SALES_LINE,
            instructions=(
                f"Connect {customer_name} with a sales specialist to complete "
                f"the plan change. Their account details and usage data have been "
                f"loaded into the call."
            ),
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {customer_name} for their time. If they need more time, "
                f"let them know they can call Nexus Mobile anytime to make the "
                f"change. Confirm that their current plan continues unchanged in "
                f"the meantime, and wish them a great day, and politely say goodbye."
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


@agent.on_action("speak_to_sales")
def handle_transfer_request(call: guava.Call) -> None:
    call.transfer(
        destination=SALES_LINE,
        instructions="Let them know you're connecting them with a Nexus Mobile specialist now.",
    )


@agent.on_outbound_failed
def on_outbound_failed(event: OutboundCallFailed) -> None:
    logging.error("Outbound call failed: %s (code %d)", event.error_reason, event.error_code)


@agent.on_session_end
def on_session_end(call: guava.Call, event: BotSessionEnded) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "use_case": "plan_upgrade",
        "customer_name": call.get_variable("customer_name"),
        "account_number": call.get_variable("account_number"),
        "plan": call.get_variable("plan"),
        "usage_pattern": call.get_variable("usage_pattern"),
        "dob_verified": call.get_field("dob") is not None,
        "upgrade_decision": call.get_field("upgrade_decision"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound plan upgrade/optimization call for Nexus Mobile"
    )
    parser.add_argument("phone", help="Customer phone number to call")
    parser.add_argument("--name", required=True, help="Customer full name")
    parser.add_argument(
        "--account-number",
        required=True,
        help="Account number (try NXM-770011, NXM-770022, or NXM-770033)",
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
