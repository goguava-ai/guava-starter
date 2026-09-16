# SDK conformance: guava-sdk 0.44.0 (2026-09-15)
import argparse
import json
import logging
from datetime import datetime, timezone

import guava
from guava import logging_utils
from guava.helpers.llm import IntentRecognizer
from guava.events import BotSessionEnded, OutboundCallFailed


# ---------------------------------------------------------------------------
# Mock API — simulates an order and tracking backend for demo purposes
# ---------------------------------------------------------------------------

MOCK_ORDERS = {
    "SWS-20260501": {
        "customer": "Maria Santos",
        "order_value": 1200.00,
        "items": "2x monitors, 1x desktop workstation",
        "delivery_date": "2026-06-28",
        "delivery_address": "4521 Commerce Dr, Dallas, TX 75201",
        "carrier": "SwiftShip Ground",
        "signature_on_file": "M. Santos",
    },
    "SWS-20260712": {
        "customer": "David Park",
        "order_value": 8500.00,
        "items": "Hydraulic press components (3 crates)",
        "delivery_date": "2026-07-15",
        "delivery_address": "8900 Industrial Blvd, Miami, FL 33142",
        "carrier": "SwiftShip Freight",
        "signature_on_file": None,
    },
    "SWS-20260830": {
        "customer": "Rachel Kim",
        "order_value": 350.00,
        "items": "Printer paper (5 cases), toner cartridges (4x)",
        "delivery_date": "2026-07-20",
        "delivery_address": "1200 Market St, Suite 400, Denver, CO 80202",
        "carrier": "SwiftShip Express",
        "signature_on_file": "R. Kim",
    },
}

HIGH_VALUE_THRESHOLD = 5000.00

SUPERVISOR_LINE = "+15552000200"


def lookup_order(tracking_number):
    return MOCK_ORDERS.get(tracking_number)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

agent = guava.Agent(
    name="Rowan",
    organization="SwiftShip Logistics - Customer Support",
    purpose=(
        "assist customers disputing a delivery, verify their order, classify "
        "the dispute type, collect evidence, and route to the appropriate "
        "resolution path"
    ),
)

_mid_call_intent = IntentRecognizer({
    "speak_to_supervisor": "The caller wants to speak to a supervisor, manager, or escalate their case",
    "withdraw": "The caller wants to stop the process, hang up, or call back later",
})


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "verify_order",
        objective=(
            "Verify the caller's order before collecting dispute details. "
            "Collect their name and tracking number. Do not discuss resolution "
            "options until the order is verified."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling SwiftShip Logistics Customer Support. "
                "I understand you have a concern about a delivery. I'll help you "
                "get this resolved. First, let me look up your order."
            ),
            guava.Field(
                key="caller_name",
                description="The full name of the customer filing the dispute",
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="tracking_number",
                description="The tracking number for the disputed shipment (format: SWS-XXXXXXXX)",
                field_type="text",
                required=True,
            ),
        ],
    )


@agent.on_task_complete("verify_order")
def on_order_verified(call: guava.Call) -> None:
    tracking_number = call.get_field("tracking_number")
    order = lookup_order(tracking_number)

    if order is None:
        logging.warning("Order lookup failed for tracking number %s.", tracking_number)
        call.hangup(
            final_instructions=(
                "Let the caller know that the tracking number provided does not match "
                "any order in our system. Ask them to double-check the number and call "
                "back, or email support@swiftship.com with their order details, and politely say goodbye."
            )
        )
        return

    call.set_variable("tracking_number", tracking_number)
    call.set_variable("order_value", order["order_value"])

    call.add_info("order_details", {
        "tracking_number": tracking_number,
        "customer": order["customer"],
        "order_value": order["order_value"],
        "items": order["items"],
        "delivery_date": order["delivery_date"],
        "delivery_address": order["delivery_address"],
        "carrier": order["carrier"],
        "signature_on_file": order["signature_on_file"],
    })

    call.set_task(
        "classify_dispute",
        objective=(
            f"Order verified — tracking number {tracking_number}, delivered on "
            f"{order['delivery_date']} to {order['delivery_address']}. Items: "
            f"{order['items']}. Value: ${order['order_value']}. "
            f"Classify the type of dispute and collect initial details. "
            f"Do NOT promise any refunds — our team will review and get back to "
            f"them within 2 business days."
        ),
        checklist=[
            guava.Say(
                f"I've found your order. It shows a delivery on {order['delivery_date']} "
                f"to {order['delivery_address']}. Let me understand what happened."
            ),
            guava.Field(
                key="dispute_type",
                description="The type of delivery dispute",
                field_type="multiple_choice",
                choices=["wrong_item", "damaged", "missing_items", "delivery_location"],
                required=True,
            ),
            guava.Field(
                key="dispute_description",
                description="A detailed description of the issue from the customer's perspective",
                field_type="text",
                required=True,
            ),
        ],
    )


@agent.on_task_complete("classify_dispute")
def on_dispute_classified(call: guava.Call) -> None:
    dispute_type = call.get_field("dispute_type")
    tracking_number = call.get_variable("tracking_number")
    order_value = call.get_variable("order_value")

    if order_value and float(order_value) > HIGH_VALUE_THRESHOLD:
        call.transfer(
            destination=SUPERVISOR_LINE,
            instructions=(
                f"The caller has a {dispute_type} dispute on order {tracking_number} "
                f"with a value of ${order_value}, which exceeds the high-value threshold. "
                f"Let them know you're transferring them to a supervisor who can handle "
                f"their case directly. Reassure them that all information has been saved."
            ),
        )
        return

    if dispute_type == "wrong_item":
        call.set_task(
            "wrong_item_resolution",
            objective=(
                f"The customer received the wrong item for order {tracking_number}. "
                f"Collect details about what they received versus what they ordered, "
                f"and arrange for a replacement. Do NOT promise refunds — our team "
                f"will review and get back to them within 2 business days."
            ),
            checklist=[
                guava.Field(
                    key="item_received",
                    description="What item the customer actually received",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="item_expected",
                    description="What item the customer expected to receive",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="callback_number",
                    description="The best phone number for follow-up",
                    field_type="text",
                    required=True,
                ),
            ],
        )
    elif dispute_type == "damaged":
        call.set_task(
            "damaged_resolution",
            objective=(
                f"The customer reports damage to order {tracking_number}. "
                f"Collect damage details and guide them on photo documentation. "
                f"Do NOT promise refunds — our team will review and get back to "
                f"them within 2 business days."
            ),
            checklist=[
                guava.Field(
                    key="damage_description",
                    description="A description of the damage to the items and packaging",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="photos_available",
                    description=(
                        "Whether the customer has photos of the damage. If not, instruct "
                        "them to take clear photos of the items and packaging and email "
                        "them to support@swiftship.com with their tracking number."
                    ),
                    field_type="multiple_choice",
                    choices=["yes", "no"],
                    required=True,
                ),
                guava.Field(
                    key="callback_number",
                    description="The best phone number for follow-up",
                    field_type="text",
                    required=True,
                ),
            ],
        )
    elif dispute_type == "missing_items":
        call.set_task(
            "missing_items_resolution",
            objective=(
                f"The customer reports missing items from order {tracking_number}. "
                f"Collect details on what is missing and open an investigation. "
                f"Do NOT promise refunds — our team will review and get back to "
                f"them within 2 business days."
            ),
            checklist=[
                guava.Field(
                    key="items_received",
                    description="What items the customer did receive",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="items_missing",
                    description="What items are missing from the order",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="callback_number",
                    description="The best phone number for follow-up",
                    field_type="text",
                    required=True,
                ),
            ],
        )
    else:
        call.set_task(
            "delivery_location_resolution",
            objective=(
                f"The customer disputes the delivery location for order {tracking_number}. "
                f"Verify the address on file and collect details about where the package "
                f"was expected versus where it was delivered. Do NOT promise refunds — "
                f"our team will review and get back to them within 2 business days."
            ),
            checklist=[
                guava.Field(
                    key="expected_address",
                    description="The address where the customer expected delivery",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="delivery_location_issue",
                    description=(
                        "What specifically is wrong with the delivery location "
                        "(left in wrong spot, wrong address entirely, etc.)"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="callback_number",
                    description="The best phone number for follow-up",
                    field_type="text",
                    required=True,
                ),
            ],
        )


def _close_dispute(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            f"Thank {call.get_field('caller_name')} for their patience. Let them know "
            f"their dispute has been logged and our team will review and get back to "
            f"them within 2 business days at the callback number provided. They can "
            f"also email support@swiftship.com with any additional information. "
            f"Apologize for the inconvenience and wish them a good day, and politely say goodbye."
        )
    )


@agent.on_task_complete("wrong_item_resolution")
def on_wrong_item_done(call: guava.Call) -> None:
    _close_dispute(call)


@agent.on_task_complete("damaged_resolution")
def on_damaged_done(call: guava.Call) -> None:
    _close_dispute(call)


@agent.on_task_complete("missing_items_resolution")
def on_missing_items_done(call: guava.Call) -> None:
    _close_dispute(call)


@agent.on_task_complete("delivery_location_resolution")
def on_delivery_location_done(call: guava.Call) -> None:
    _close_dispute(call)


@agent.on_question
def on_question(call: guava.Call, question: str) -> str:
    return (
        "I'm not able to make determinations about refunds or replacements during "
        "this call. Our team will review all the details and get back to you within "
        "2 business days. For now, let's make sure we have all the information about "
        "what happened."
    )


@agent.on_action_request
def on_action_request(call: guava.Call, intent_summary: str):
    return _mid_call_intent.classify(intent_summary)


@agent.on_action("speak_to_supervisor")
def handle_transfer(call: guava.Call) -> None:
    call.transfer(
        destination=SUPERVISOR_LINE,
        instructions=(
            "Let the caller know you're connecting them with a supervisor now. "
            "Reassure them that any information collected so far has been saved."
        ),
    )


@agent.on_action("withdraw")
def handle_withdraw(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            "Let them know that's completely fine. They can call back anytime or "
            "email support@swiftship.com with their tracking number and details. "
            "Wish them well, and politely say goodbye."
        )
    )


@agent.on_session_end
def on_session_end(call: guava.Call, event: BotSessionEnded) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "use_case": "delivery_dispute",
        "caller_name": call.get_field("caller_name"),
        "tracking_number": call.get_variable("tracking_number"),
        "order_value": call.get_variable("order_value"),
        "dispute_type": call.get_field("dispute_type"),
        "dispute_description": call.get_field("dispute_description"),
        "item_received": call.get_field("item_received"),
        "damage_description": call.get_field("damage_description"),
        "items_missing": call.get_field("items_missing"),
        "callback_number": call.get_field("callback_number"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()

    parser = argparse.ArgumentParser(
        description="Inbound delivery dispute agent for SwiftShip Logistics"
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
