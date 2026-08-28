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
# Mock API — simulates a cart/order backend for demo purposes
# ---------------------------------------------------------------------------

MOCK_CARTS = {
    "CART-10001": {
        "customer": "Priya Sharma",
        "items": "Wireless earbuds, Phone case, USB-C cable",
        "total": "$87.49",
        "abandonment_reason": "price_concern",
    },
    "CART-10002": {
        "customer": "Marcus Webb",
        "items": "Running shoes (size 11), Moisture-wicking socks (3-pack)",
        "total": "$134.95",
        "abandonment_reason": "shipping",
    },
    "CART-10003": {
        "customer": "Elena Cortez",
        "items": "Standing desk converter, Monitor arm",
        "total": "$289.00",
        "abandonment_reason": "changed_mind",
    },
    "CART-10004": {
        "customer": "James Liu",
        "items": "Bluetooth speaker, Charging pad",
        "total": "$62.50",
        "abandonment_reason": "technical_issue",
    },
}


def lookup_cart(cart_id):
    return MOCK_CARTS.get(cart_id)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

agent = guava.Agent(
    name="Kai",
    organization="ShopNow",
    purpose=(
        "reach out to customers who left items in their cart, understand "
        "their reason for not completing the purchase, address their concern, "
        "and help them complete the order when appropriate"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
    "speak_to_support": "The caller wants to speak to a customer support representative or real person",
})

SUPPORT_LINE = "+15559001010"


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(
        contact_full_name=call.get_variable("customer_name"),
        voicemail_message=(
            f"Hi, this is Kai from ShopNow calling for "
            f"{call.get_variable('customer_name')}. We noticed you left some items "
            f"in your cart and wanted to check if there's anything we can help with. "
            f"No action needed — call us back anytime. Thank you!"
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    customer_name = call.get_variable("customer_name")
    cart_id = call.get_variable("cart_id")

    if outcome == "available":
        cart = lookup_cart(cart_id)
        if cart is None:
            logging.warning("Cart %s not found.", cart_id)
            call.hangup(
                final_instructions=(
                    "Apologize and let the customer know we encountered an issue "
                    "retrieving their cart information. Suggest they visit shopnow.com "
                    "to view their saved cart, and politely say goodbye."
                )
            )
            return

        call.set_variable("cart_items", cart["items"])
        call.set_variable("cart_total", cart["total"])
        call.set_variable("abandonment_reason", cart["abandonment_reason"])

        call.add_info("cart_details", {
            "cart_id": cart_id,
            "items": cart["items"],
            "total": cart["total"],
            "abandonment_reason": cart["abandonment_reason"],
        })

        call.set_task(
            "identify_concern",
            objective=(
                f"Reach out to {customer_name} about their abandoned ShopNow cart "
                f"({cart_id}) containing {cart['items']} totaling {cart['total']}. "
                f"Understand why they didn't complete their purchase. Be helpful "
                f"and low-pressure."
            ),
            checklist=[
                guava.Say(
                    f"I noticed you had some great items saved in your cart — "
                    f"{cart['items']} — totaling {cart['total']}. I just wanted to "
                    f"check in and see if there was anything I could help with."
                ),
                guava.Field(
                    key="stated_reason",
                    description=(
                        "The reason the customer gives for not completing their "
                        "purchase, in their own words"
                    ),
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
                "again and their preference has been recorded, and politely say goodbye."
            )
        )
    elif outcome == "wrong_number":
        logging.info("Wrong number reached for %s.", customer_name)
        call.hangup(final_instructions="Apologize for the mistake and wish them well, and politely say goodbye.")
    else:
        logging.info("Could not reach %s (outcome: %s).", customer_name, outcome)
        call.hangup()


@agent.on_task_complete("identify_concern")
def on_concern_identified(call: guava.Call) -> None:
    abandonment_reason = call.get_variable("abandonment_reason")
    stated_reason = call.get_field("stated_reason")
    customer_name = call.get_variable("customer_name")
    cart_total = call.get_variable("cart_total")

    if stated_reason and "changed" in stated_reason.lower() and "mind" in stated_reason.lower():
        call.hangup(
            final_instructions=(
                f"Thank {customer_name} for letting you know. Let them know their "
                f"cart will stay saved for 30 days and they can come back anytime. "
                f"No pressure — wish them a great day, and politely say goodbye."
            )
        )
        return

    if abandonment_reason == "price_concern":
        call.set_task(
            "address_concern",
            objective=(
                f"{customer_name} had a price concern about their {cart_total} cart. "
                f"Offer a 15%% discount code (SAVE15) they can apply at checkout. "
                f"Do not push if they decline — one offer only."
            ),
            checklist=[
                guava.Say(
                    f"I completely understand. I'd love to offer you a special 15%% "
                    f"discount code — SAVE15 — that you can apply at checkout. That "
                    f"would bring your total down."
                ),
                guava.Field(
                    key="offer_response",
                    description="Whether the customer accepted the discount offer",
                    field_type="multiple_choice",
                    choices=["accepted", "declined", "thinking_about_it"],
                    required=True,
                ),
            ],
        )
    elif abandonment_reason == "shipping":
        call.set_task(
            "address_concern",
            objective=(
                f"{customer_name} had a shipping concern. Explain ShopNow's free "
                f"shipping threshold ($75+) and expedited shipping options. Their "
                f"cart at {cart_total} may already qualify for free shipping."
            ),
            checklist=[
                guava.Say(
                    f"ShopNow offers free standard "
                    f"shipping on all orders over $75, and your cart is at {cart_total}, "
                    f"so you'd qualify. We also have expedited options if you need it sooner."
                ),
                guava.Field(
                    key="offer_response",
                    description="Whether the shipping explanation resolved the customer's concern",
                    field_type="multiple_choice",
                    choices=["accepted", "declined", "thinking_about_it"],
                    required=True,
                ),
            ],
        )
    elif abandonment_reason == "changed_mind":
        call.hangup(
            final_instructions=(
                f"Thank {customer_name} for letting you know. Let them know their "
                f"cart will stay saved for 30 days and they can come back anytime. "
                f"No pressure — wish them a great day, and politely say goodbye."
            )
        )
        return
    elif abandonment_reason == "technical_issue":
        call.set_task(
            "address_concern",
            objective=(
                f"{customer_name} experienced a technical issue during checkout. "
                f"Offer to help them complete the order by phone, or transfer them "
                f"to support if they'd prefer."
            ),
            checklist=[
                guava.Say(
                    f"I'm sorry to hear you ran into a technical issue. I can help "
                    f"you complete your order right now over the phone, or I can "
                    f"connect you with our support team if you'd prefer."
                ),
                guava.Field(
                    key="offer_response",
                    description=(
                        "Whether the customer wants to complete the order by phone, "
                        "be transferred to support, or handle it themselves"
                    ),
                    field_type="multiple_choice",
                    choices=["complete_by_phone", "transfer_to_support", "will_try_again"],
                    required=True,
                ),
            ],
        )
    else:
        call.set_task(
            "address_concern",
            objective=(
                f"Address {customer_name}'s concern about their cart. Listen to "
                f"their reason and offer appropriate help."
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


@agent.on_task_complete("address_concern")
def on_concern_addressed(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    offer_response = call.get_field("offer_response")

    if offer_response == "transfer_to_support":
        call.transfer(
            destination=SUPPORT_LINE,
            instructions=(
                "Let the customer know you're connecting them with ShopNow support "
                "now. Their cart information has been saved."
            ),
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {customer_name} for their time. If they accepted an offer, "
                f"confirm the discount code or next steps. If they need more time, "
                f"let them know their cart is saved and the ShopNow team is available "
                f"anytime, and wish them a great day, and politely say goodbye."
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


@agent.on_action("speak_to_support")
def handle_transfer_request(call: guava.Call) -> None:
    call.transfer(
        destination=SUPPORT_LINE,
        instructions="Let them know you're connecting them with ShopNow support now.",
    )


@agent.on_outbound_failed
def on_outbound_failed(event: OutboundCallFailed) -> None:
    logging.error("Outbound call failed: %s (code %d)", event.error_reason, event.error_code)


@agent.on_session_end
def on_session_end(call: guava.Call, event: BotSessionEnded) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "use_case": "cart_recovery",
        "customer_name": call.get_variable("customer_name"),
        "cart_id": call.get_variable("cart_id"),
        "cart_items": call.get_variable("cart_items"),
        "cart_total": call.get_variable("cart_total"),
        "abandonment_reason": call.get_variable("abandonment_reason"),
        "stated_reason": call.get_field("stated_reason"),
        "offer_response": call.get_field("offer_response"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound cart recovery call for ShopNow"
    )
    parser.add_argument("phone", help="Customer phone number to call")
    parser.add_argument("--name", required=True, help="Customer full name")
    parser.add_argument(
        "--cart-id",
        required=True,
        help="Cart ID (try CART-10001, CART-10002, CART-10003, or CART-10004)",
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
            "cart_id": args.cart_id,
        },
    )
