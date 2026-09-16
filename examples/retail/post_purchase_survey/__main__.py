# SDK conformance: guava-sdk 0.43.0 (2026-09-15)
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
    name="Remy",
    organization="ShopNow",
    purpose=(
        "collect structured feedback about a customer's recent purchase experience, "
        "probe deeper on low ratings for product or delivery, and thank them for "
        "their time"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
    "speak_to_someone": "The caller wants to speak to a real person or customer service representative",
})


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(
        contact_full_name=call.get_variable("customer_name"),
        voicemail_message=(
            f"Hi, this is Remy from ShopNow calling for "
            f"{call.get_variable('customer_name')}. We'd love to hear about your "
            f"recent order experience. No action needed — feel free to call us back "
            f"at your convenience. Thank you!"
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    customer_name = call.get_variable("customer_name")
    product_name = call.get_variable("product_name")
    order_number = call.get_variable("order_number")

    if outcome == "available":
        call.set_task(
            "survey",
            objective=(
                f"Conduct a brief post-purchase satisfaction survey with "
                f"{customer_name} regarding order #{order_number} for "
                f"'{product_name}'. Collect product and delivery ratings on a "
                f"1-to-5 scale. Keep the tone friendly, brief, and appreciative."
            ),
            checklist=[
                guava.Say(
                    f"I'm calling because you recently received your order of "
                    f"'{product_name}', order number {order_number}. We'd love just "
                    f"two minutes of your time to hear how everything went."
                ),
                guava.Field(
                    key="product_rating",
                    description=(
                        "Customer's product satisfaction rating on a scale of 1 to 5, "
                        "where 1 is very dissatisfied and 5 is extremely satisfied"
                    ),
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="delivery_rating",
                    description=(
                        "Customer's delivery experience rating on a scale of 1 to 5, "
                        "including packaging, timeliness, and item condition"
                    ),
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="would_recommend",
                    description="Whether the customer would recommend ShopNow to a friend",
                    field_type="multiple_choice",
                    choices=["yes", "no", "maybe"],
                    required=True,
                ),
            ],
        )
    elif outcome == "do_not_contact":
        logging.info("Customer %s requested no further contact.", customer_name)
        call.hangup(
            final_instructions=(
                "Acknowledge their request politely. Let them know they have been "
                "removed from our outreach list and will not be contacted again, and politely say goodbye."
            )
        )
    elif outcome == "wrong_number":
        logging.info("Wrong number reached for %s.", customer_name)
        call.hangup(final_instructions="Apologize for the mistake and wish them well, and politely say goodbye.")
    else:
        logging.info("Could not reach %s (outcome: %s).", customer_name, outcome)
        call.hangup()


@agent.on_task_complete("survey")
def on_survey_done(call: guava.Call) -> None:
    product_rating = call.get_field("product_rating")
    delivery_rating = call.get_field("delivery_rating")
    customer_name = call.get_variable("customer_name")

    if product_rating is not None and product_rating <= 2:
        call.set_task(
            "low_product_probe",
            objective=(
                f"{customer_name} gave a low product rating ({product_rating}/5). "
                f"Ask what specifically was disappointing about the product. Listen "
                f"carefully and be empathetic. Let them know their feedback will be "
                f"shared with the product team."
            ),
            checklist=[
                guava.Field(
                    key="product_issue_details",
                    description="What specifically the customer was unhappy about with the product",
                    field_type="text",
                    required=True,
                ),
            ],
        )
    elif delivery_rating is not None and delivery_rating <= 2:
        call.set_task(
            "low_delivery_probe",
            objective=(
                f"{customer_name} gave a low delivery rating ({delivery_rating}/5). "
                f"Ask what specifically went wrong with the delivery experience. "
                f"Listen carefully and be empathetic."
            ),
            checklist=[
                guava.Field(
                    key="delivery_issue_details",
                    description="What specifically was wrong with the delivery experience",
                    field_type="text",
                    required=True,
                ),
            ],
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {customer_name} sincerely for their feedback. Let them know "
                f"their responses help improve the ShopNow experience. Wish them a "
                f"wonderful day, and politely say goodbye."
            )
        )


@agent.on_task_complete("low_product_probe")
def on_product_probe_done(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    delivery_rating = call.get_field("delivery_rating")

    if delivery_rating is not None and delivery_rating <= 2:
        call.set_task(
            "low_delivery_probe",
            objective=(
                f"{customer_name} also gave a low delivery rating ({delivery_rating}/5). "
                f"Ask what specifically went wrong with the delivery experience."
            ),
            checklist=[
                guava.Field(
                    key="delivery_issue_details",
                    description="What specifically was wrong with the delivery experience",
                    field_type="text",
                    required=True,
                ),
            ],
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {customer_name} for sharing that feedback — it genuinely helps. "
                f"Assure them that their product concerns will be reviewed by the team. "
                f"Wish them a good day, and politely say goodbye."
            )
        )


@agent.on_task_complete("low_delivery_probe")
def on_delivery_probe_done(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    call.hangup(
        final_instructions=(
            f"Thank {customer_name} for sharing that feedback. Assure them their "
            f"concerns will be reviewed, and wish them a good day, and politely say goodbye."
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


@agent.on_action("speak_to_someone")
def handle_speak_to_someone(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            "Let them know that a ShopNow team member will call them back within "
            "one business day. Ask if there's a preferred time and thank them, and politely say goodbye."
        )
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
        "order_number": call.get_variable("order_number"),
        "product_rating": call.get_field("product_rating"),
        "delivery_rating": call.get_field("delivery_rating"),
        "would_recommend": call.get_field("would_recommend"),
        "product_issue_details": call.get_field("product_issue_details"),
        "delivery_issue_details": call.get_field("delivery_issue_details"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound post-purchase survey call for ShopNow"
    )
    parser.add_argument("phone", help="Customer phone number to call")
    parser.add_argument("--name", required=True, help="Customer full name")
    parser.add_argument("--product-name", required=True, help="Name of the purchased product")
    parser.add_argument("--order-number", required=True, help="Order number")
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
            "order_number": args.order_number,
        },
    )
