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

agent = guava.Agent(
    name="Tatum",
    organization="ShopNow — Customer Safety Team",
    purpose=(
        "urgently notify customers affected by a product recall, provide "
        "safety instructions specific to the product category, and arrange "
        "a return or replacement"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
    "speak_to_someone": "The caller wants to speak to a safety specialist or customer service representative",
})


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    product_name = call.get_variable("product_name")
    customer_name = call.get_variable("customer_name")
    call.reach_person(
        contact_full_name=customer_name,
        voicemail_message=(
            f"Hi, this is Tatum from the ShopNow Customer Safety Team with an "
            f"urgent message for {customer_name}. We have issued a recall for "
            f"'{product_name}'. Please stop using this product immediately and "
            f"call us back at 1-800-555-0199 as soon as possible for important "
            f"safety information. Thank you."
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    customer_name = call.get_variable("customer_name")
    product_name = call.get_variable("product_name")
    product_category = call.get_variable("product_category")
    recall_reason = call.get_variable("recall_reason")
    order_number = call.get_variable("order_number")

    if outcome == "available":
        if product_category == "electronics":
            safety_instructions = (
                "Unplug the product immediately and do not attempt to use or charge it. "
                "Keep it away from flammable materials. Package it carefully for return."
            )
            disposal_note = (
                "Do not dispose of electronics in regular trash. We will provide a "
                "prepaid return label for safe recycling."
            )
        elif product_category == "food":
            safety_instructions = (
                "Do not consume any remaining product. Check your refrigerator and "
                "pantry for additional units. Dispose of the product in a sealed bag "
                "in your household trash."
            )
            disposal_note = (
                "No return is needed for food items. Your refund will be processed "
                "automatically."
            )
        elif product_category == "children":
            safety_instructions = (
                "Remove the product from any area accessible to children immediately. "
                "Do not allow children to use or play with the product under any "
                "circumstances. Store it out of reach until returned."
            )
            disposal_note = (
                "We will send a prepaid return label. Please do not donate or give "
                "away the product."
            )
        else:
            safety_instructions = (
                "Stop using the product immediately as a precaution. Store it "
                "safely until you receive return instructions."
            )
            disposal_note = (
                "We will provide return instructions and a prepaid shipping label."
            )

        call.set_task(
            "recall_notification",
            objective=(
                f"Urgently notify {customer_name} that '{product_name}' from order "
                f"#{order_number} is subject to recall due to: {recall_reason}. "
                f"Provide category-specific safety instructions: {safety_instructions} "
                f"{disposal_note} Confirm they understand and arrange resolution."
            ),
            checklist=[
                guava.Say(
                    f"I'm reaching out with an important safety notice about "
                    f"'{product_name}' from your order #{order_number}. We have "
                    f"issued a recall due to: {recall_reason}. {safety_instructions}"
                ),
                guava.Field(
                    key="recall_acknowledged",
                    description="Whether the customer has understood the recall and safety instructions",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="product_status",
                    description="Whether the customer still has the product and its current state",
                    field_type="multiple_choice",
                    choices=["in_use", "stored", "discarded", "given_away"],
                    required=True,
                ),
                guava.Field(
                    key="resolution_choice",
                    description="The customer's preferred resolution for the recalled product",
                    field_type="multiple_choice",
                    choices=["return_refund", "replacement", "store_credit"],
                    required=True,
                ),
            ],
        )
    elif outcome == "do_not_contact":
        logging.info("Customer %s requested no further contact.", customer_name)
        call.hangup(
            final_instructions=(
                "Acknowledge their request. Note that this was a safety-related call. "
                "Let them know they will not be contacted again but can call "
                "1-800-555-0199 for recall information, and politely say goodbye."
            )
        )
    elif outcome == "wrong_number":
        logging.info("Wrong number reached for %s.", customer_name)
        call.hangup(final_instructions="Apologize for the mistake and wish them well, and politely say goodbye.")
    else:
        logging.info("Could not reach %s (outcome: %s).", customer_name, outcome)
        call.hangup()


@agent.on_task_complete("recall_notification")
def on_recall_done(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    call.hangup(
        final_instructions=(
            f"Thank {customer_name} for taking this matter seriously. Confirm their "
            f"chosen resolution has been recorded. Let them know they will receive "
            f"next steps within 24 hours. Provide the safety hotline number "
            f"1-800-555-0199 for any further questions. Emphasize that their safety "
            f"is ShopNow's highest priority, and politely say goodbye."
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
            "contact list. Mention the safety hotline 1-800-555-0199 is available "
            "if they need recall information in the future, and politely say goodbye."
        )
    )


@agent.on_action("speak_to_someone")
def handle_speak_to_someone(call: guava.Call) -> None:
    call.transfer(
        destination="+18005550199",
        instructions="Let them know you're connecting them with a safety specialist now.",
    )


@agent.on_outbound_failed
def on_outbound_failed(event: OutboundCallFailed) -> None:
    logging.error("Outbound call failed: %s (code %d)", event.error_reason, event.error_code)


@agent.on_session_end
def on_session_end(call: guava.Call, event: BotSessionEnded) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "customer_name": call.get_variable("customer_name"),
        "product_name": call.get_variable("product_name"),
        "product_category": call.get_variable("product_category"),
        "recall_reason": call.get_variable("recall_reason"),
        "order_number": call.get_variable("order_number"),
        "recall_acknowledged": call.get_field("recall_acknowledged"),
        "product_status": call.get_field("product_status"),
        "resolution_choice": call.get_field("resolution_choice"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound product recall notification call for ShopNow"
    )
    parser.add_argument("phone", help="Customer phone number to call")
    parser.add_argument("--name", required=True, help="Customer full name")
    parser.add_argument("--product-name", required=True, help="Name of the recalled product")
    parser.add_argument(
        "--product-category",
        required=True,
        choices=["electronics", "food", "children", "other"],
        help="Product category (determines safety instructions)",
    )
    parser.add_argument(
        "--recall-reason", required=True, help="Reason for the recall"
    )
    parser.add_argument("--order-number", required=True, help="Customer's order number")
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
            "product_name": args.product_name,
            "product_category": args.product_category,
            "recall_reason": args.recall_reason,
            "order_number": args.order_number,
        },
    )
