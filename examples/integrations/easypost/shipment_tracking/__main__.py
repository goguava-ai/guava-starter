import logging
import os

import guava
import requests
from guava import logging_utils

EASYPOST_API_KEY = os.environ["EASYPOST_API_KEY"]
BASE_URL = "https://api.easypost.com/v2"


agent = guava.Agent(
    name="Maya",
    organization="Whitetail Crafts",
    purpose="to help customers check on their shipment status",
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "shipment_tracking",
        objective="Look up the customer's shipment and provide a clear status update, including current location and estimated delivery date if available.",
        checklist=[
            guava.Say(
                "Thanks for calling Whitetail Crafts. This is Maya. I can help you track your shipment today."
            ),
            guava.Field(
                key="tracking_number",
                field_type="text",
                description="Ask the customer for their tracking number. It may be found on their order confirmation email or packing slip.",
                required=True,
            ),
            guava.Field(
                key="carrier",
                field_type="multiple_choice",
                description="Ask which carrier the customer believes the package was shipped with, if they know. This helps narrow down the lookup.",
                choices=["UPS", "USPS", "FedEx", "DHL", "unknown"],
                required=False,
            ),
        ],
    )


@agent.on_task_complete("shipment_tracking")
def on_done(call: guava.Call) -> None:
    tracking_number = call.get_field("tracking_number")
    carrier = call.get_field("carrier")

    params = {"tracking_code": tracking_number}
    if carrier and carrier.lower() != "unknown":
        params["carrier"] = carrier

    tracker = None
    try:
        resp = requests.get(
            f"{BASE_URL}/trackers",
            auth=(EASYPOST_API_KEY, ""),
            params=params,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        trackers = data.get("trackers", [])

        if trackers:
            tracker = trackers[0]
        else:
            tracker = None
    except Exception as e:
        logging.error("EasyPost API error fetching trackers: %s", e)
        tracker = None

    if tracker:
        status = tracker.get("status", "unknown")
        est_delivery = tracker.get("est_delivery_date")
        tracking_details = tracker.get("tracking_details", [])
        latest_detail = tracking_details[-1] if tracking_details else None

        location_str = ""
        if latest_detail:
            loc = latest_detail.get("tracking_location", {})
            city = loc.get("city", "")
            state = loc.get("state", "")
            if city and state:
                location_str = f"Last seen in {city}, {state}."

        delivery_str = ""
        if est_delivery:
            delivery_str = f"Estimated delivery: {est_delivery}."

        call.hangup(
            final_instructions=(
                f"Tell the customer their shipment status is '{status}'. "
                f"{location_str} {delivery_str} "
                "If the status is 'delivered', confirm it was delivered. "
                "If 'in_transit' or 'out_for_delivery', be encouraging. "
                "If 'failure' or 'return_to_sender', express empathy and suggest they contact support. "
                "Be warm, friendly, and concise."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Tell the customer you were unable to find a shipment with tracking number '{tracking_number}'. "
                "Suggest they double-check the number from their confirmation email, or offer to transfer them to a support agent. "
                "Be apologetic and helpful."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
