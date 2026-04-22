import argparse
import json
import logging
import os
from datetime import datetime, timezone

import guava
import requests
from guava import logging_utils

STORE_HASH = os.environ["BIGCOMMERCE_STORE_HASH"]
AUTH_TOKEN = os.environ["BIGCOMMERCE_AUTH_TOKEN"]
V3_BASE = f"https://api.bigcommerce.com/stores/{STORE_HASH}/v3"

HEADERS = {
    "X-Auth-Token": AUTH_TOKEN,
    "Content-Type": "application/json",
    "Accept": "application/json",
}


agent = guava.Agent(
    name="Riley",
    organization="Harbor House",
    purpose="to reconnect with Harbor House customers who left items in their cart and help them complete their purchase",
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    cart_id = call.get_variable("cart_id")
    cart_total = call.get_variable("cart_total")

    # Attempt to fetch cart line items so the agent can mention specific products
    line_items_summary = ""
    try:
        resp = requests.get(
            f"{V3_BASE}/abandoned-carts/{cart_id}",
            headers=HEADERS,
            timeout=10,
        )
        resp.raise_for_status()
        cart_data = resp.json()
        line_items = (
            cart_data.get("data", {}).get("cart", {}).get("line_items", {})
            or cart_data.get("data", {}).get("line_items", {})
            or {}
        )
        physical = line_items.get("physical_items", [])
        digital = line_items.get("digital_items", [])
        all_items = physical + digital
        if all_items:
            parts = []
            for item in all_items[:5]:
                name = item.get("name", "item")
                qty = item.get("quantity", 1)
                parts.append(f"{qty}x {name}")
            line_items_summary = ", ".join(parts)
            logging.info("Cart line items fetched: %s", line_items_summary)
    except Exception as e:
        logging.warning("Could not fetch cart details for cart %s: %s", cart_id, e)

    call.set_variable("line_items_summary", line_items_summary)

    call.reach_person(contact_full_name=customer_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    if outcome == "unavailable":
        customer_name = call.get_variable("customer_name")
        cart_total = call.get_variable("cart_total")
        logging.info(
            "Could not reach %s for cart recovery. Leaving voicemail.",
            customer_name,
        )
        call.hangup(
            final_instructions=(
                f"Leave a brief, friendly voicemail for {customer_name}. "
                "Introduce yourself as Riley from Harbor House. Let them know they left some "
                f"great items worth {cart_total} in their cart and that it's still saved "
                "for them at harborhouse.com whenever they're ready. "
                "Let them know they can call back with any questions. Keep it short and upbeat."
            )
        )
    elif outcome == "available":
        customer_name = call.get_variable("customer_name")
        cart_total = call.get_variable("cart_total")
        line_items_summary = call.get_variable("line_items_summary") or ""

        items_mention = (
            f" — including {line_items_summary} —"
            if line_items_summary
            else ""
        )

        call.set_task(
            "cart_recovery",
            objective=(
                f"You've reached {customer_name}, a Harbor House customer who left "
                f"{cart_total} worth of items{items_mention} in their cart. "
                "Greet them warmly, mention the cart, and find out how you can help them "
                "complete the purchase or address any concerns."
            ),
            checklist=[
                guava.Say(
                    f"Hi {customer_name}, this is Riley calling from Harbor House. "
                    f"I'm reaching out because it looks like you left some great items{items_mention} "
                    f"worth {cart_total} in your cart. I just wanted to check in and see if "
                    "there's anything I can help you with to complete your order."
                ),
                guava.Field(
                    key="customer_response",
                    description=(
                        "Find out how you can help the customer. Ask what brought them to abandon "
                        "the cart. Offer these options and capture their choice: "
                        "'yes, I'd like to complete it', 'had questions about an item', "
                        "'changed my mind', 'had a payment issue'."
                    ),
                    field_type="multiple_choice",
                    choices=[
                        "yes, I'd like to complete it",
                        "had questions about an item",
                        "changed my mind",
                        "had a payment issue",
                    ],
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("cart_recovery")
def on_cart_recovery_done(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    customer_email = call.get_variable("customer_email")
    cart_id = call.get_variable("cart_id")

    response = call.get_field("customer_response")
    label = (response or "").strip().lower()

    if "complete it" in label:
        call.hangup(
            final_instructions=(
                f"Let {customer_name} know that their cart is saved and ready for them. "
                "Offer to transfer them to the Harbor House sales team so they can complete "
                "the order by phone, or let them know they can finish checkout by visiting "
                "harborhouse.com — their cart will still be there. "
                "Thank them for shopping with Harbor House and wish them a great day."
            )
        )
    elif "questions" in label:
        call.set_task(
            "cart_product_questions",
            objective=(
                f"{customer_name} has questions about one of the items in their cart. "
                "Find out what they'd like to know and answer if possible, or arrange to connect "
                "them with a product specialist."
            ),
            checklist=[
                guava.Field(
                    key="question_about",
                    description=(
                        "Ask the customer what their question is about — which product and "
                        "what specifically they'd like to know (size, material, compatibility, etc.). "
                        "Capture their question in full."
                    ),
                    field_type="text",
                    required=True,
                ),
            ],
        )
    elif "changed" in label:
        call.set_task(
            "cart_changed_mind",
            objective=(
                f"{customer_name} has changed their mind about the purchase. "
                "Understand why and — if price was the issue — offer a discount code."
            ),
            checklist=[
                guava.Field(
                    key="changed_mind_reason",
                    description=(
                        "Ask why they decided not to complete the order. "
                        "Offer these options: 'too expensive', 'found it elsewhere', "
                        "'don't need it anymore'."
                    ),
                    field_type="multiple_choice",
                    choices=["too expensive", "found it elsewhere", "don't need it anymore"],
                    required=True,
                ),
            ],
        )
    elif "payment" in label:
        call.hangup(
            final_instructions=(
                f"Apologize to {customer_name} for the trouble and let them know you can "
                "help them complete the order over the phone right now if they'd like — offer "
                "to transfer them to the Harbor House sales team to process payment securely. "
                "Alternatively, direct them to harborhouse.com/help/payments for guidance on "
                "supported payment methods and troubleshooting steps. "
                "Let them know their cart is saved so no items will be lost. "
                "Thank them for their patience."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                "Thank the customer for their time and let them know their cart is saved "
                "at harborhouse.com whenever they're ready. Wish them a great day."
            )
        )


@agent.on_task_complete("cart_product_questions")
def on_product_questions_done(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    customer_email = call.get_variable("customer_email")
    cart_id = call.get_variable("cart_id")

    question = call.get_field("question_about")
    print(json.dumps({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "customer_name": customer_name,
        "customer_email": customer_email,
        "cart_id": cart_id,
        "outcome": "product_question",
        "question": question,
    }, indent=2))
    logging.info("Cart recovery — product question logged for %s.", customer_name)
    call.hangup(
        final_instructions=(
            f"Address {customer_name}'s question about '{question}' based on product details. "
            "If unable to fully address the question, transfer them to a Harbor House "
            "product specialist who can provide complete details. "
            "Thank them for calling and let them know their cart is saved."
        )
    )


@agent.on_task_complete("cart_changed_mind")
def on_changed_mind_done(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    customer_email = call.get_variable("customer_email")
    cart_id = call.get_variable("cart_id")

    reason = call.get_field("changed_mind_reason")
    print(json.dumps({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "customer_name": customer_name,
        "customer_email": customer_email,
        "cart_id": cart_id,
        "outcome": "changed_mind",
        "reason": reason,
    }, indent=2))
    logging.info("Cart recovery — customer changed mind, reason: %s.", reason)

    reason_lower = (reason or "").lower()
    if "expensive" in reason_lower or "price" in reason_lower:
        call.hangup(
            final_instructions=(
                f"Empathize with {customer_name} about the price. "
                "Let them know you'd like to offer them a discount on their order — "
                "share the code SAVE10 which gives them 10% off their cart. "
                "Let them know the code can be entered at checkout on harborhouse.com "
                "and that their cart is still saved. "
                "Thank them warmly for giving Harbor House another chance."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {customer_name} for their time and for letting you know. "
                "Let them know that Harbor House always has new arrivals and that they're "
                "welcome to visit harborhouse.com any time. Wish them a great day."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Harbor House abandoned cart recovery agent"
    )
    parser.add_argument("phone", help="Customer phone number to call (E.164 format)")
    parser.add_argument("--name", required=True, help="Customer full name")
    parser.add_argument("--email", required=True, help="Customer email address")
    parser.add_argument("--cart-id", required=True, help="BigCommerce abandoned cart token/ID")
    parser.add_argument(
        "--cart-total",
        required=True,
        help="Human-readable cart total, e.g. '$89.99'",
    )
    args = parser.parse_args()

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "customer_name": args.name,
            "customer_email": args.email,
            "cart_id": args.cart_id,
            "cart_total": args.cart_total,
        },
    )
