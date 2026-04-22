import guava
import os
import logging
from guava import logging_utils
import json
import argparse
from datetime import datetime, timezone


agent = guava.Agent(
    name="Casey",
    organization="SwiftShip Logistics - Dispatch",
    purpose=(
        "perform a status check-in on load number, "
        "collect current location, ETA, and load status for TMS update"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    load_number = call.get_variable("load_number")
    destination = call.get_variable("destination")
    scheduled_arrival = call.get_variable("scheduled_arrival")
    call.set_task(
        "carrier_checkin",
        objective=(
            f"Check in with the driver or carrier contact regarding load number {load_number} "
            f"headed to {destination}. The scheduled arrival is {scheduled_arrival}. "
            "Collect the driver's name, current location, estimated arrival time, and current load status. "
            "If there is a delay, get the reason. Also note any remaining loads on this run."
        ),
        checklist=[
            guava.Say(
                f"Hi, this is Casey calling from SwiftShip Logistics Dispatch. "
                f"I'm reaching out for a status update on load number {load_number} "
                f"heading to {destination}, originally scheduled to arrive {scheduled_arrival}."
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
    )


@agent.on_task_complete("carrier_checkin")
def on_done(call: guava.Call) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "load_number": call.get_variable("load_number"),
        "destination": call.get_variable("destination"),
        "scheduled_arrival": call.get_variable("scheduled_arrival"),
        "driver_name": call.get_field("driver_name"),
        "current_location": call.get_field("current_location"),
        "estimated_arrival_time": call.get_field("estimated_arrival_time"),
        "load_status": call.get_field("load_status"),
        "delay_reason": call.get_field("delay_reason"),
        "loads_remaining": call.get_field("loads_remaining"),
    }
    print(json.dumps(results, indent=2))
    logging.info("Carrier check-in results saved.")
    call.hangup(
        final_instructions=(
            "Thank the driver for the update and let them know SwiftShip Dispatch will "
            "relay the ETA to the shipper. If there is a delay or an issue, assure them "
            "that dispatch will follow up with any necessary support. Wish them a safe drive."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(description="SwiftShip Logistics - Carrier Check-In Agent")
    parser.add_argument("phone", help="Driver or carrier phone number to call")
    parser.add_argument("--load-number", required=True, help="Load or shipment number")
    parser.add_argument("--destination", required=True, help="Delivery destination")
    parser.add_argument("--scheduled-arrival", required=True, help="Originally scheduled arrival time/date")
    args = parser.parse_args()

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "load_number": args.load_number,
            "destination": args.destination,
            "scheduled_arrival": args.scheduled_arrival,
        },
    )
