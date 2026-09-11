# SDK conformance: guava-sdk 0.42.0 (2026-09-08)
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
    name="Sage",
    organization="ShopNow",
    purpose=(
        "proactively notify customers about the status of their order — whether "
        "shipped, delayed, or experiencing an issue — and provide relevant details "
        "or connect them with support"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
    "speak_to_someone": "The caller wants to speak to a real person or customer support representative",
})


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(
        contact_full_name=call.get_variable("customer_name"),
        voicemail_message=(
            f"Hi, this is Sage from ShopNow calling for "
            f"{call.get_variable('customer_name')} with an update on order "
            f"#{call.get_variable('order_number')}. No action needed — please call "
            f"us back at your convenience for details. Thank you!"
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    customer_name = call.get_variable("customer_name")
    order_number = call.get_variable("order_number")
    order_state = call.get_variable("order_state")

    if outcome == "available":
        if order_state == "shipped":
            tracking_number = call.get_variable("tracking_number")
            eta = call.get_variable("eta")
            call.set_task(
                "deliver_shipped_update",
                objective=(
                    f"Notify {customer_name} that order #{order_number} has shipped. "
                    f"Provide tracking number {tracking_number} and estimated delivery "
                    f"date of {eta}. Confirm they received the information clearly."
                ),
                checklist=[
                    guava.Say(
                        f"Great news — your order #{order_number} has shipped! Your "
                        f"tracking number is {tracking_number} and the estimated "
                        f"delivery date is {eta}."
                    ),
                    guava.Field(
                        key="update_acknowledged",
                        description="Whether the customer understood the shipping update and tracking info",
                        field_type="text",
                        required=True,
                    ),
                    guava.Field(
                        key="additional_questions",
                        description="Any additional questions the customer has about their shipment",
                        field_type="text",
                        required=False,
                    ),
                ],
            )
        elif order_state == "delayed":
            delay_reason = call.get_variable("delay_reason")
            new_eta = call.get_variable("new_eta")
            call.set_task(
                "deliver_delay_update",
                objective=(
                    f"Notify {customer_name} that order #{order_number} has been delayed. "
                    f"Explain the reason: {delay_reason}. Provide the new estimated "
                    f"delivery date of {new_eta}. Be empathetic and apologetic."
                ),
                checklist=[
                    guava.Say(
                        f"I'm calling with an update on your order #{order_number}. "
                        f"Unfortunately, there has been a delay due to {delay_reason}. "
                        f"Your new estimated delivery date is {new_eta}. We sincerely "
                        f"apologize for the inconvenience."
                    ),
                    guava.Field(
                        key="update_acknowledged",
                        description="Whether the customer understood the delay and new timeline",
                        field_type="text",
                        required=True,
                    ),
                    guava.Field(
                        key="additional_questions",
                        description="Any concerns or questions about the delay",
                        field_type="text",
                        required=False,
                    ),
                ],
            )
        else:
            issue_description = call.get_variable("issue_description")
            call.set_task(
                "deliver_issue_update",
                objective=(
                    f"Notify {customer_name} that there is an issue with order "
                    f"#{order_number}: {issue_description}. Let them know we need to "
                    f"connect them with our support team to resolve this. Be empathetic."
                ),
                checklist=[
                    guava.Say(
                        f"I'm calling about your order #{order_number}. Unfortunately, "
                        f"we've encountered an issue: {issue_description}. I'd like to "
                        f"connect you with our support team who can help resolve this "
                        f"for you."
                    ),
                    guava.Field(
                        key="update_acknowledged",
                        description="Whether the customer understood the issue",
                        field_type="text",
                        required=True,
                    ),
                    guava.Field(
                        key="wants_transfer",
                        description="Whether the customer wants to be transferred to support now",
                        field_type="multiple_choice",
                        choices=["yes", "no", "callback_later"],
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


@agent.on_task_complete("deliver_shipped_update")
def on_shipped_done(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            f"Thank {call.get_variable('customer_name')} for their time. Let them "
            f"know they can track their package using the tracking number provided. "
            f"Wish them a great day, and politely say goodbye."
        )
    )


@agent.on_task_complete("deliver_delay_update")
def on_delay_done(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            f"Thank {call.get_variable('customer_name')} for their patience. "
            f"Remind them they can reach ShopNow support at 1-555-900-1001 or "
            f"shopnow.com/support with any questions about their order, "
            f"and politely say goodbye."
        )
    )


@agent.on_task_complete("deliver_issue_update")
def on_issue_done(call: guava.Call) -> None:
    wants_transfer = call.get_field("wants_transfer")

    if wants_transfer == "yes":
        call.transfer(
            destination="+15559001001",
            instructions=(
                "Let the customer know you're connecting them with ShopNow support now. "
                "Reassure them that their order details have been saved."
            ),
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {call.get_variable('customer_name')} for their time. If they "
                f"requested a callback, confirm a support agent will reach out within "
                f"one business day, and wish them a great day, and politely say goodbye."
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
    call.transfer(
        destination="+15559001001",
        instructions="Let them know you're connecting them with ShopNow support now.",
    )


@agent.on_outbound_failed
def on_outbound_failed(event: OutboundCallFailed) -> None:
    logging.error("Outbound call failed: %s (code %d)", event.error_reason, event.error_code)


@agent.on_session_end
def on_session_end(call: guava.Call, event: BotSessionEnded) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "customer_name": call.get_variable("customer_name"),
        "order_number": call.get_variable("order_number"),
        "order_state": call.get_variable("order_state"),
        "update_acknowledged": call.get_field("update_acknowledged"),
        "additional_questions": call.get_field("additional_questions"),
        "wants_transfer": call.get_field("wants_transfer"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound order status update call for ShopNow"
    )
    parser.add_argument("phone", help="Customer phone number to call")
    parser.add_argument("--name", required=True, help="Customer full name")
    parser.add_argument("--order-number", required=True, help="Order number")
    parser.add_argument(
        "--order-state",
        required=True,
        choices=["shipped", "delayed", "issue"],
        help="Current state of the order",
    )
    parser.add_argument("--tracking-number", default="", help="Tracking number (for shipped orders)")
    parser.add_argument("--eta", default="", help="Estimated delivery date (for shipped orders)")
    parser.add_argument("--delay-reason", default="", help="Reason for delay (for delayed orders)")
    parser.add_argument("--new-eta", default="", help="New estimated date (for delayed orders)")
    parser.add_argument("--issue-description", default="", help="Issue description (for issue orders)")
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
            "order_number": args.order_number,
            "order_state": args.order_state,
            "tracking_number": args.tracking_number,
            "eta": args.eta,
            "delay_reason": args.delay_reason,
            "new_eta": args.new_eta,
            "issue_description": args.issue_description,
        },
    )
