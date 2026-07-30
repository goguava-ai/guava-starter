# SDK conformance: guava-sdk 0.35.0 (2026-07-21)
import argparse
import json
import logging
from datetime import datetime, timezone

import guava
from guava import logging_utils
from guava.helpers.llm import IntentRecognizer


# ---------------------------------------------------------------------------
# Mock API — simulates a shipment backend for demo purposes
# ---------------------------------------------------------------------------

MOCK_SHIPMENTS = {
    "SWS-20260501": {
        "recipient": "Maria Santos",
        "delivery_date": "2026-06-28",
        "origin": "Los Angeles, CA",
        "destination": "Dallas, TX",
        "declared_value": 1200.00,
        "item_description": "Electronics — 2x monitors, 1x desktop workstation",
    },
    "SWS-20260712": {
        "recipient": "David Park",
        "delivery_date": "2026-07-15",
        "origin": "Chicago, IL",
        "destination": "Miami, FL",
        "declared_value": 8500.00,
        "item_description": "Industrial equipment — hydraulic press components",
    },
    "SWS-20260830": {
        "recipient": "Rachel Kim",
        "delivery_date": "2026-07-20",
        "origin": "Seattle, WA",
        "destination": "Denver, CO",
        "declared_value": 350.00,
        "item_description": "Office supplies — printer paper, toner cartridges",
    },
}

HIGH_VALUE_THRESHOLD = 5000.00

CLAIMS_TEAM_LINE = "+15552000100"


def lookup_shipment(tracking_number):
    return MOCK_SHIPMENTS.get(tracking_number)


def create_claim(tracking_number, damage_type, details):
    claim_number = f"DMG-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}"
    logging.info("[MOCK API] POST /claims — created %s for shipment %s", claim_number, tracking_number)
    return claim_number


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

agent = guava.Agent(
    name="Harper",
    organization="SwiftShip Logistics - Claims",
    purpose=(
        "assist customers reporting damaged goods, verify their shipment, "
        "classify the damage, collect claim details, and route high-value "
        "claims to the claims team"
    ),
)

_mid_call_intent = IntentRecognizer({
    "speak_to_claims": "The caller wants to speak to a claims specialist or live person",
    "withdraw": "The caller wants to stop the process, hang up, or call back later",
})


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "verify_shipment",
        objective=(
            "Verify the caller's shipment before collecting any claim details. "
            "Collect their name and tracking number. Do not discuss claim options "
            "or timelines until the shipment is verified."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling SwiftShip Logistics Claims. I'm sorry to hear "
                "about the damage to your shipment. I'll help you get a claim started. "
                "First, I need to look up your shipment."
            ),
            guava.Field(
                key="caller_name",
                description="The full name of the person filing the damage claim",
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="tracking_number",
                description="The tracking number for the damaged shipment (format: SWS-XXXXXXXX)",
                field_type="text",
                required=True,
            ),
        ],
    )


@agent.on_task_complete("verify_shipment")
def on_shipment_verified(call: guava.Call) -> None:
    tracking_number = call.get_field("tracking_number")
    shipment = lookup_shipment(tracking_number)

    if shipment is None:
        logging.warning("Shipment lookup failed for tracking number %s.", tracking_number)
        call.hangup(
            final_instructions=(
                "Let the caller know that the tracking number provided does not match "
                "any shipment in our system. Ask them to double-check the number on "
                "their delivery confirmation and call back. They can also email "
                "claims@swiftship.com with photos and their tracking number, and politely say goodbye."
            )
        )
        return

    call.set_variable("tracking_number", tracking_number)
    call.set_variable("declared_value", shipment["declared_value"])

    call.add_info("shipment_details", {
        "tracking_number": tracking_number,
        "recipient": shipment["recipient"],
        "delivery_date": shipment["delivery_date"],
        "origin": shipment["origin"],
        "destination": shipment["destination"],
        "declared_value": shipment["declared_value"],
        "item_description": shipment["item_description"],
    })

    call.set_task(
        "classify_damage",
        objective=(
            f"Shipment verified — tracking number {tracking_number}, delivered on "
            f"{shipment['delivery_date']}. Items: {shipment['item_description']}. "
            f"Now classify the type and extent of damage. "
            f"Do NOT promise any specific refund amount or timeline — all claims "
            f"are subject to review by the claims team."
        ),
        checklist=[
            guava.Say(
                f"I've found your shipment. It was delivered on {shipment['delivery_date']} "
                f"from {shipment['origin']} to {shipment['destination']}. "
                f"Now let me collect the details about the damage."
            ),
            guava.Field(
                key="damage_type",
                description="The extent of damage to the shipment",
                field_type="multiple_choice",
                choices=["minor", "major", "total_loss"],
                required=True,
            ),
            guava.Field(
                key="damage_description",
                description="A description of the damage observed on the items and packaging",
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="packaging_condition",
                description="The condition of the outer packaging when received",
                field_type="multiple_choice",
                choices=["intact", "damaged", "destroyed"],
                required=True,
            ),
            guava.Field(
                key="photos_available",
                description="Whether the caller has photos of the damage available to submit",
                field_type="multiple_choice",
                choices=["yes", "no"],
                required=True,
            ),
        ],
    )


@agent.on_task_complete("classify_damage")
def on_damage_classified(call: guava.Call) -> None:
    damage_type = call.get_field("damage_type")
    tracking_number = call.get_variable("tracking_number")
    declared_value = call.get_variable("declared_value")

    details = {
        "damage_type": damage_type,
        "damage_description": call.get_field("damage_description"),
        "packaging_condition": call.get_field("packaging_condition"),
    }
    claim_number = create_claim(tracking_number, damage_type, details)
    call.set_variable("claim_number", claim_number)

    if damage_type == "total_loss" or (declared_value and float(declared_value) > HIGH_VALUE_THRESHOLD):
        call.transfer(
            destination=CLAIMS_TEAM_LINE,
            instructions=(
                f"The caller has reported a {damage_type} claim on shipment "
                f"{tracking_number} with a declared value of ${declared_value}. "
                f"Claim number {claim_number} has been created. Let them know you're "
                f"transferring them to a claims specialist who can guide them through "
                f"the next steps. Reassure them that all information collected so far "
                f"has been saved."
            ),
        )
        return

    if damage_type == "major":
        call.set_task(
            "major_damage_resolution",
            objective=(
                f"Claim {claim_number} has been filed for major damage on shipment "
                f"{tracking_number}. Collect the caller's preferred resolution and "
                f"a callback number. Do NOT promise a specific refund amount — all "
                f"claims are subject to review."
            ),
            checklist=[
                guava.Field(
                    key="replacement_requested",
                    description="Whether the caller would like a replacement shipment arranged",
                    field_type="multiple_choice",
                    choices=["yes", "no"],
                    required=True,
                ),
                guava.Field(
                    key="callback_number",
                    description="The best phone number to reach the caller for follow-up",
                    field_type="text",
                    required=True,
                ),
            ],
        )
    else:
        call.set_task(
            "minor_damage_resolution",
            objective=(
                f"Claim {claim_number} has been filed for minor damage on shipment "
                f"{tracking_number}. Let the caller know the claim will be reviewed "
                f"and they will hear back within 3 to 5 business days. Collect a "
                f"callback number. Do NOT promise a specific refund amount — all "
                f"claims are subject to review."
            ),
            checklist=[
                guava.Field(
                    key="callback_number",
                    description="The best phone number to reach the caller for follow-up",
                    field_type="text",
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("major_damage_resolution")
def on_major_done(call: guava.Call) -> None:
    claim_number = call.get_variable("claim_number")
    call.hangup(
        final_instructions=(
            f"Let the caller know their claim number is {claim_number}. A claims "
            f"specialist will review the case and contact them within 2 business "
            f"days. If they requested a replacement, let them know the team will "
            f"confirm availability during follow-up. Thank them for their patience, and politely say goodbye."
        )
    )


@agent.on_task_complete("minor_damage_resolution")
def on_minor_done(call: guava.Call) -> None:
    claim_number = call.get_variable("claim_number")
    call.hangup(
        final_instructions=(
            f"Let the caller know their claim number is {claim_number}. The claims "
            f"team will review and respond within 3 to 5 business days at the "
            f"callback number provided. If they have photos, remind them to email "
            f"them to claims@swiftship.com referencing claim {claim_number}. "
            f"Thank them and apologize for the inconvenience, and politely say goodbye."
        )
    )


@agent.on_question
def on_question(call: guava.Call, question: str) -> str:
    return (
        "I'm not able to make any determinations about refund amounts or claim "
        "outcomes. The claims team will review all the details and get back to "
        "you with a resolution. For now, let's make sure we capture everything "
        "about the damage."
    )


@agent.on_action_request
def on_action_request(call: guava.Call, intent_summary: str):
    return _mid_call_intent.classify(intent_summary)


@agent.on_action("speak_to_claims")
def handle_transfer(call: guava.Call) -> None:
    call.transfer(
        destination=CLAIMS_TEAM_LINE,
        instructions=(
            "Let the caller know you're connecting them with a claims specialist "
            "now. Reassure them that any information collected so far has been saved."
        ),
    )


@agent.on_action("withdraw")
def handle_withdraw(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            "Let them know that's completely fine. They can call back anytime to "
            "continue filing their claim. If they have photos of the damage, suggest "
            "they email them to claims@swiftship.com, and wish them well, and politely say goodbye."
        )
    )


@agent.on_session_end
def on_session_end(call: guava.Call, event: guava.BotSessionEnded) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "use_case": "damaged_goods_claim",
        "caller_name": call.get_field("caller_name"),
        "tracking_number": call.get_variable("tracking_number"),
        "claim_number": call.get_variable("claim_number"),
        "damage_type": call.get_field("damage_type"),
        "damage_description": call.get_field("damage_description"),
        "packaging_condition": call.get_field("packaging_condition"),
        "photos_available": call.get_field("photos_available"),
        "replacement_requested": call.get_field("replacement_requested"),
        "callback_number": call.get_field("callback_number"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()

    parser = argparse.ArgumentParser(
        description="Inbound damaged goods claim agent for SwiftShip Logistics"
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
