import guava
import os
import logging
import json
import argparse
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)


class DeliveryDisputeController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="SwiftShip Logistics - Customer Support",
            agent_name="Sam",
            agent_purpose=(
                "assist customers calling to dispute a delivery, collect structured details about "
                "the incident, and route the case to the appropriate resolution team"
            ),
        )

        self.set_task(
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
                    description=(
                        "The category of the delivery dispute: "
                        "not_received (package never arrived), "
                        "wrong_item (incorrect item delivered), "
                        "stolen (package was stolen after delivery), "
                        "damaged (item arrived damaged), "
                        "or late (delivery arrived significantly past the expected date)"
                    ),
                    field_type="text",
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
                    description=(
                        "The customer's preferred resolution: "
                        "reship (send the item again), "
                        "refund (receive a full refund), "
                        "or investigation (have SwiftShip investigate the incident)"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="best_callback_number",
                    description="The best phone number to reach the customer when the resolution team follows up",
                    field_type="text",
                    required=True,
                ),
            ],
            on_complete=self.save_results,
        )

        self.accept_call()

    def save_results(self):
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "claimant_name": self.get_field("claimant_name"),
            "tracking_number": self.get_field("tracking_number"),
            "dispute_type": self.get_field("dispute_type"),
            "order_value": self.get_field("order_value"),
            "dispute_description": self.get_field("dispute_description"),
            "resolution_preference": self.get_field("resolution_preference"),
            "best_callback_number": self.get_field("best_callback_number"),
        }
        print(json.dumps(results, indent=2))
        logging.info("Delivery dispute results saved.")
        self.hangup(
            final_instructions=(
                "Thank the customer sincerely for their patience and for providing all the details. "
                "Assure them that their dispute has been logged and will be reviewed by a specialist "
                "on the SwiftShip resolution team. Let them know they can expect a follow-up call "
                "or email within 1 to 2 business days. Apologize for the inconvenience caused and "
                "wish them a good day."
            )
        )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=DeliveryDisputeController,
    )
