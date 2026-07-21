# SDK conformance: guava-sdk 0.34.0 (2026-07-14)
import json
import logging
import argparse
from datetime import datetime, timezone

import guava
from guava import logging_utils

agent = guava.Agent(
    name="Sam",
    organization="SwiftShip Logistics - Customer Support",
    purpose=(
        "assist customers calling to dispute a delivery, collect structured details about "
        "the incident, and route the case to the appropriate resolution team"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "delivery_dispute",
        objective=(
            "Greet the caller and help them file a delivery dispute. Collect their name, "
            "tracking number, the type of dispute they are experiencing, the order value, "
            "a description of what happened, their preferred resolution, and the best "
            "callback number so the resolution team can follow up."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling SwiftShip Logistics Customer Support. "
                "I understand you're calling about a delivery issue. "
                "I'm here to help and I'll get all the details recorded so our team can "
                "work on a resolution as quickly as possible."
            ),
            guava.Field(
                key="claimant_name",
                description="The full name of the customer calling to file the delivery dispute",
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="tracking_number",
                description="The tracking number for the shipment that is being disputed",
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="dispute_type",
                description="The category of the delivery dispute",
                field_type="multiple_choice",
                choices=["not_received", "wrong_item", "stolen", "damaged", "late"],
                required=True,
            ),
            guava.Field(
                key="order_value",
                description="The total value of the order being disputed, including currency",
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="dispute_description",
                description="A detailed description of what happened with the delivery from the customer's perspective",
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="resolution_preference",
                description="The customer's preferred resolution for the dispute",
                field_type="multiple_choice",
                choices=["reship", "refund", "investigation"],
                required=True,
            ),
            guava.Field(
                key="best_callback_number",
                description="The best phone number to reach the customer when the resolution team follows up",
                field_type="text",
                required=True,
            ),
        ],
    )


@agent.on_task_complete("delivery_dispute")
def on_done(call: guava.Call) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "claimant_name": call.get_field("claimant_name"),
        "tracking_number": call.get_field("tracking_number"),
        "dispute_type": call.get_field("dispute_type"),
        "order_value": call.get_field("order_value"),
        "dispute_description": call.get_field("dispute_description"),
        "resolution_preference": call.get_field("resolution_preference"),
        "best_callback_number": call.get_field("best_callback_number"),
    }
    print(json.dumps(results, indent=2))
    logging.info("Delivery dispute results saved.")
    call.hangup(
        final_instructions=(
            "Thank the customer sincerely for their patience and for providing all the details. "
            "Assure them that their dispute has been logged and will be reviewed by a specialist "
            "on the SwiftShip resolution team. Let them know they can expect a follow-up call "
            "or email within 1 to 2 business days. Apologize for the inconvenience caused and "
            "wish them a good day."
        )
    )


@agent.on_session_end
def on_session_end(call: guava.Call) -> None:
    logging.info("Session ended — collected fields: %s", json.dumps({
        "claimant_name": call.get_field("claimant_name"),
        "tracking_number": call.get_field("tracking_number"),
        "dispute_type": call.get_field("dispute_type"),
        "order_value": call.get_field("order_value"),
        "dispute_description": call.get_field("dispute_description"),
        "resolution_preference": call.get_field("resolution_preference"),
        "best_callback_number": call.get_field("best_callback_number"),
    }, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()

    parser = argparse.ArgumentParser()
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
