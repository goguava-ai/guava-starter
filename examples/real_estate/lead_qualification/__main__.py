# SDK conformance: guava-sdk 0.35.0 (2026-07-21)
import argparse
import json
import logging
from datetime import datetime, timezone

import guava
from guava import logging_utils
from guava.helpers.llm import IntentRecognizer


# ---------------------------------------------------------------------------
# Mock API — simulates an active listings backend for demo purposes
# ---------------------------------------------------------------------------

MOCK_LISTINGS = {
    "downtown": [
        {"address": "450 Main St, Unit 12", "price": 425000, "beds": 2, "baths": 2, "type": "condo"},
        {"address": "88 Commerce Ave", "price": 615000, "beds": 3, "baths": 2, "type": "townhouse"},
    ],
    "westside": [
        {"address": "2201 Sunset Blvd", "price": 789000, "beds": 4, "baths": 3, "type": "single_family"},
        {"address": "1540 Oak Lane", "price": 520000, "beds": 3, "baths": 2, "type": "single_family"},
    ],
    "north_hills": [
        {"address": "310 Ridgeview Dr", "price": 1250000, "beds": 5, "baths": 4, "type": "single_family"},
    ],
}

AGENT_LINE = "+15553000100"


def search_listings(area):
    area_key = area.lower().replace(" ", "_")
    return MOCK_LISTINGS.get(area_key, [])


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

agent = guava.Agent(
    name="Finley",
    organization="Acme Realty Group",
    purpose=(
        "qualify inbound real estate leads by classifying their intent, "
        "collecting requirements based on whether they want to buy, sell, "
        "or rent, and connecting qualified leads with an agent"
    ),
)

_mid_call_intent = IntentRecognizer({
    "buy": "The caller wants to buy a property or home",
    "sell": "The caller wants to sell a property or home they own",
    "rent": "The caller wants to rent an apartment, house, or unit",
    "speak_to_agent": "The caller wants to speak to a real estate agent or live person",
    "withdraw": "The caller wants to stop the process, hang up, or call back later",
})


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "classify_intent",
        objective=(
            "Welcome the caller and determine whether they are interested in "
            "buying, selling, or renting a property. Collect their name and "
            "classify their intent before gathering detailed requirements."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Acme Realty Group! My name is Finley, "
                "and I'm here to help connect you with the right agent for your "
                "needs. This will just take a few minutes."
            ),
            guava.Field(
                key="caller_name",
                description="The caller's full name",
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="intent",
                description="Whether the caller is looking to buy, sell, or rent",
                field_type="multiple_choice",
                choices=["buy", "sell", "rent"],
                required=True,
            ),
        ],
    )


@agent.on_task_complete("classify_intent")
def on_intent_classified(call: guava.Call) -> None:
    intent = call.get_field("intent")
    caller_name = call.get_field("caller_name")
    call.set_variable("caller_name", caller_name)
    call.set_variable("intent", intent)

    if intent == "buy":
        call.set_task(
            "collect_buyer_requirements",
            objective=(
                f"{caller_name} is looking to buy. Collect their budget, desired "
                f"bedrooms and bathrooms, target area, timeline, and whether they "
                f"are pre-approved for financing. Be conversational and helpful."
            ),
            checklist=[
                guava.Field(
                    key="budget_range",
                    description="The caller's budget or price range for purchasing",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="bedrooms",
                    description="The desired number of bedrooms",
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="bathrooms",
                    description="The desired number of bathrooms",
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="target_area",
                    description="The preferred city, neighborhood, or area",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="timeline",
                    description=(
                        "The caller's timeline for purchasing (within 30 days, "
                        "3 months, 6 months, open-ended, etc.)"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="pre_approved",
                    description="Whether the caller has been pre-approved for a mortgage",
                    field_type="multiple_choice",
                    choices=["yes", "no", "paying_cash"],
                    required=True,
                ),
            ],
        )
    elif intent == "sell":
        call.set_task(
            "collect_seller_requirements",
            objective=(
                f"{caller_name} is looking to sell. Collect details about the "
                f"property they want to sell, their timeline, and whether it is "
                f"currently listed with another agent."
            ),
            checklist=[
                guava.Field(
                    key="property_address",
                    description="The address of the property the caller wants to sell",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="property_type",
                    description="The type of property being sold",
                    field_type="multiple_choice",
                    choices=["single_family", "condo", "townhouse", "multi_family", "land"],
                    required=True,
                ),
                guava.Field(
                    key="bedrooms",
                    description="The number of bedrooms in the property",
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="bathrooms",
                    description="The number of bathrooms in the property",
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="timeline",
                    description="When the caller wants to sell (ASAP, within 3 months, flexible, etc.)",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="currently_listed",
                    description="Whether the property is currently listed with another agent",
                    field_type="multiple_choice",
                    choices=["yes", "no"],
                    required=True,
                ),
            ],
        )
    else:
        call.set_task(
            "collect_renter_requirements",
            objective=(
                f"{caller_name} is looking to rent. Collect their budget, "
                f"preferred move-in date, target area, and whether they have pets."
            ),
            checklist=[
                guava.Field(
                    key="monthly_budget",
                    description="The caller's monthly budget for rent",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="target_area",
                    description="The preferred city, neighborhood, or area",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="move_in_date",
                    description="The caller's preferred move-in date",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="pets",
                    description="Whether the caller has pets and what type",
                    field_type="text",
                    required=True,
                ),
            ],
        )


def _qualify_and_route(call: guava.Call) -> None:
    caller_name = call.get_variable("caller_name")
    intent = call.get_variable("intent")

    call.add_info("lead_summary", {
        "caller_name": caller_name,
        "intent": intent,
        "target_area": call.get_field("target_area"),
        "budget_range": call.get_field("budget_range"),
        "monthly_budget": call.get_field("monthly_budget"),
        "timeline": call.get_field("timeline"),
        "pre_approved": call.get_field("pre_approved"),
    })

    qualified = False
    if intent == "buy" and call.get_field("pre_approved") in ("yes", "paying_cash"):
        qualified = True
    elif intent == "sell":
        qualified = True
    elif intent == "rent" and call.get_field("monthly_budget"):
        qualified = True

    if qualified:
        call.transfer(
            destination=AGENT_LINE,
            instructions=(
                f"This is a qualified {intent} lead. {caller_name} has provided "
                f"all required details. Let them know you're connecting them with "
                f"an agent who specializes in their area and needs. Reassure them "
                f"that all their information has been saved."
            ),
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {caller_name} for their interest in Acme Realty Group. "
                f"Let them know an agent will follow up within one business day to "
                f"discuss their needs in detail. If they are looking to buy, suggest "
                f"getting pre-approved as a helpful first step, and wish them well, and politely say goodbye."
            )
        )


@agent.on_task_complete("collect_buyer_requirements")
def on_buyer_done(call: guava.Call) -> None:
    _qualify_and_route(call)


@agent.on_task_complete("collect_seller_requirements")
def on_seller_done(call: guava.Call) -> None:
    _qualify_and_route(call)


@agent.on_task_complete("collect_renter_requirements")
def on_renter_done(call: guava.Call) -> None:
    _qualify_and_route(call)


@agent.on_question
def on_question(call: guava.Call, question: str) -> str:
    return (
        "Your agent will have those details during the showing or consultation. "
        "For now, let me make sure we capture your requirements so we can match "
        "you with the right person."
    )


@agent.on_action_request
def on_action_request(call: guava.Call, intent_summary: str):
    return _mid_call_intent.classify(intent_summary)


@agent.on_action("buy")
def handle_buy_intent(call: guava.Call) -> None:
    call.set_variable("intent", "buy")


@agent.on_action("sell")
def handle_sell_intent(call: guava.Call) -> None:
    call.set_variable("intent", "sell")


@agent.on_action("rent")
def handle_rent_intent(call: guava.Call) -> None:
    call.set_variable("intent", "rent")


@agent.on_action("speak_to_agent")
def handle_transfer(call: guava.Call) -> None:
    call.transfer(
        destination=AGENT_LINE,
        instructions=(
            "Let the caller know you're connecting them with an agent now. "
            "Reassure them that any information collected so far has been saved."
        ),
    )


@agent.on_action("withdraw")
def handle_withdraw(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            "Let them know that's completely fine. An agent can follow up at their "
            "convenience. They can also browse listings at pinnaclerealtygroup.com. "
            "Wish them well, and politely say goodbye."
        )
    )


@agent.on_session_end
def on_session_end(call: guava.Call, event: guava.BotSessionEnded) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "use_case": "lead_qualification",
        "caller_name": call.get_variable("caller_name"),
        "intent": call.get_variable("intent"),
        "budget_range": call.get_field("budget_range"),
        "monthly_budget": call.get_field("monthly_budget"),
        "bedrooms": call.get_field("bedrooms"),
        "bathrooms": call.get_field("bathrooms"),
        "target_area": call.get_field("target_area"),
        "timeline": call.get_field("timeline"),
        "pre_approved": call.get_field("pre_approved"),
        "property_address": call.get_field("property_address"),
        "property_type": call.get_field("property_type"),
        "currently_listed": call.get_field("currently_listed"),
        "move_in_date": call.get_field("move_in_date"),
        "pets": call.get_field("pets"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()

    parser = argparse.ArgumentParser(
        description="Inbound lead qualification agent for Acme Realty Group"
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
