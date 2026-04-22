import guava
import os
import logging
from guava import logging_utils
import json
import argparse
from datetime import datetime, timezone


agent = guava.Agent(
    name="Morgan",
    organization="SwiftShip Logistics - Claims",
    purpose=(
        "assist customers who are calling to report damaged goods received through SwiftShip Logistics, "
        "collect all necessary claim details, and create a structured damage claim case"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "damaged_goods_claim",
        objective=(
            "Greet the caller and assist them in filing a damaged goods claim. "
            "Collect their name, tracking number, delivery date, a description of the damage, "
            "the number of damaged items, packaging condition, photo availability, "
            "their preference for replacement or refund, and a callback number for follow-up."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling SwiftShip Logistics Claims department. "
                "I'm sorry to hear about the damage to your shipment. "
                "I'll help you file a claim today and I just need to collect a few details."
            ),
            guava.Field(
                key="claimant_name",
                description="The full name of the person filing the damage claim",
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="tracking_number",
                description="The tracking number associated with the damaged shipment",
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="delivery_date",
                description="The date the damaged shipment was delivered",
                field_type="date",
                required=True,
            ),
            guava.Field(
                key="damage_description",
                description="A description of the damage observed on the items or package",
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="number_of_damaged_items",
                description="The total number of individual items that were damaged",
                field_type="integer",
                required=True,
            ),
            guava.Field(
                key="packaging_condition",
                description="The condition of the outer packaging when the shipment was received: intact, damaged, or destroyed",
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="photos_available",
                description="Whether the claimant has photos of the damaged items or packaging available to submit",
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="replacement_or_refund_preference",
                description="Whether the claimant prefers a replacement shipment or a refund to resolve the claim",
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="callback_number",
                description="The best phone number to reach the claimant for follow-up on this claim",
                field_type="text",
                required=True,
            ),
        ],
    )


@agent.on_task_complete("damaged_goods_claim")
def on_done(call: guava.Call) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "claimant_name": call.get_field("claimant_name"),
        "tracking_number": call.get_field("tracking_number"),
        "delivery_date": call.get_field("delivery_date"),
        "damage_description": call.get_field("damage_description"),
        "number_of_damaged_items": call.get_field("number_of_damaged_items"),
        "packaging_condition": call.get_field("packaging_condition"),
        "photos_available": call.get_field("photos_available"),
        "replacement_or_refund_preference": call.get_field("replacement_or_refund_preference"),
        "callback_number": call.get_field("callback_number"),
    }
    print(json.dumps(results, indent=2))
    logging.info("Damaged goods claim results saved.")
    call.hangup(
        final_instructions=(
            "Thank the caller for providing all the details and assure them that their claim "
            "has been recorded. Let them know a claims specialist will review their case and "
            "reach out to them within 2 to 3 business days at the callback number they provided. "
            "Apologize again for the inconvenience and wish them a good day."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
