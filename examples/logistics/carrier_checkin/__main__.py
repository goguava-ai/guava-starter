import guava
import os
import logging
import json
import argparse
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)


class CarrierCheckinController(guava.CallController):
    def __init__(self, load_number, destination, scheduled_arrival):
        super().__init__()
        self.load_number = load_number
        self.destination = destination
        self.scheduled_arrival = scheduled_arrival

        self.set_persona(
            organization_name="SwiftShip Logistics - Dispatch",
            agent_name="Casey",
            agent_purpose=(
                f"perform a status check-in on load number {self.load_number} "
                f"destined for {self.destination} with a scheduled arrival of {self.scheduled_arrival}, "
                "and collect current location, ETA, and load status for TMS update"
            ),
        )

        self.set_task(
            objective=(
                f"Check in with the driver or carrier contact regarding load number {self.load_number} "
                f"headed to {self.destination}. The scheduled arrival is {self.scheduled_arrival}. "
                "Collect the driver's name, current location, estimated arrival time, and current load status. "
                "If there is a delay, get the reason. Also note any remaining loads on this run."
            ),
            checklist=[
                guava.Say(
                    f"Hi, this is Casey calling from SwiftShip Logistics Dispatch. "
                    f"I'm reaching out for a status update on load number {self.load_number} "
                    f"heading to {self.destination}, originally scheduled to arrive {self.scheduled_arrival}."
                ),
                guava.Field(
                    key="driver_name",
                    description="The full name of the driver or carrier contact on the call",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="current_location",
                    description="The driver's current location, such as a city, highway mile marker, or landmark",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="estimated_arrival_time",
                    description="The driver's current estimated arrival time at the destination",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="load_status",
                    description="Current status of the load: on_time, delayed, delivered, or issue",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="delay_reason",
                    description="If the load is delayed or there is an issue, the reason for the delay or problem",
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="loads_remaining",
                    description="Number of additional stops or loads remaining on this run after the current destination",
                    field_type="integer",
                    required=False,
                ),
            ],
            on_complete=self.save_results,
        )

    def save_results(self):
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "load_number": self.load_number,
            "destination": self.destination,
            "scheduled_arrival": self.scheduled_arrival,
            "driver_name": self.get_field("driver_name"),
            "current_location": self.get_field("current_location"),
            "estimated_arrival_time": self.get_field("estimated_arrival_time"),
            "load_status": self.get_field("load_status"),
            "delay_reason": self.get_field("delay_reason"),
            "loads_remaining": self.get_field("loads_remaining"),
        }
        print(json.dumps(results, indent=2))
        logging.info("Carrier check-in results saved.")
        self.hangup(
            final_instructions=(
                "Thank the driver for the update and let them know SwiftShip Dispatch will "
                "relay the ETA to the shipper. If there is a delay or an issue, assure them "
                "that dispatch will follow up with any necessary support. Wish them a safe drive."
            )
        )

    def recipient_unavailable(self):
        logging.warning(
            f"Could not reach carrier contact for load number {self.load_number}."
        )
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "load_number": self.load_number,
            "destination": self.destination,
            "scheduled_arrival": self.scheduled_arrival,
            "status": "recipient_unavailable",
        }
        print(json.dumps(results, indent=2))
        self.hangup(
            final_instructions=(
                f"Leave a voicemail asking the driver to call back SwiftShip Logistics Dispatch "
                f"as soon as possible for a status update on load number {self.load_number}."
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SwiftShip Logistics - Carrier Check-In Agent")
    parser.add_argument("phone", help="Driver or carrier phone number to call")
    parser.add_argument("--load-number", required=True, help="Load or shipment number")
    parser.add_argument("--destination", required=True, help="Delivery destination")
    parser.add_argument("--scheduled-arrival", required=True, help="Originally scheduled arrival time/date")
    args = parser.parse_args()

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=CarrierCheckinController(
            load_number=args.load_number,
            destination=args.destination,
            scheduled_arrival=args.scheduled_arrival,
        ),
    )
