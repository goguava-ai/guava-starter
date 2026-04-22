import guava
import os
import logging
from guava import logging_utils
import requests


EASYPOST_API_KEY = os.environ["EASYPOST_API_KEY"]
BASE_URL = "https://api.easypost.com/v2"


def _get_tracker(tracking_number: str):
    try:
        resp = requests.get(
            f"{BASE_URL}/trackers",
            auth=(EASYPOST_API_KEY, ""),
            params={"tracking_code": tracking_number},
            timeout=10,
        )
        resp.raise_for_status()
        trackers = resp.json().get("trackers", [])
        return trackers[0] if trackers else None
    except Exception as e:
        logging.error("EasyPost error fetching tracker: %s", e)
        return None


def _get_shipment_by_tracking(tracking_number: str):
    try:
        resp = requests.get(
            f"{BASE_URL}/shipments",
            auth=(EASYPOST_API_KEY, ""),
            params={"purchased": True},
            timeout=10,
        )
        resp.raise_for_status()
        shipments = resp.json().get("shipments", [])
        for s in shipments:
            if s.get("tracking_code") == tracking_number:
                return s
    except Exception as e:
        logging.error("EasyPost error listing shipments: %s", e)
    return None


def _refund_shipment(shipment_id: str):
    try:
        resp = requests.post(
            f"{BASE_URL}/shipments/{shipment_id}/refund",
            auth=(EASYPOST_API_KEY, ""),
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logging.error("EasyPost error refunding shipment %s: %s", shipment_id, e)
        return None


agent = guava.Agent(
    name="Jordan",
    organization="Whitetail Crafts",
    purpose="to help customers resolve lost or missing package claims",
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "lost_package_claim",
        objective=(
            "Help the customer file a claim for a package that shows as delivered but was not received. "
            "Verify the delivery status, collect claim details, and process a shipping label refund."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Whitetail Crafts. This is Jordan. I'm sorry to hear you're having trouble with a delivery. I'm here to help."
            ),
            guava.Field(
                key="tracking_number",
                field_type="text",
                description="Ask the customer for their tracking number from their order confirmation.",
                required=True,
            ),
            guava.Field(
                key="delivery_address",
                field_type="text",
                description="Ask the customer to confirm the delivery address where the package was supposed to arrive.",
                required=True,
            ),
            guava.Field(
                key="checked_locations",
                field_type="multiple_choice",
                description="Ask whether the customer has already checked with neighbors, their building's mail room, or around the front door and garage.",
                choices=["yes, checked all locations", "only checked front door", "have not checked yet"],
                required=True,
            ),
            guava.Field(
                key="package_description",
                field_type="text",
                description="Ask for a brief description of the package contents and approximate value.",
                required=True,
            ),
            guava.Field(
                key="request_refund",
                field_type="multiple_choice",
                description="Explain that you can process a shipping label refund for the lost package. Ask if they would like to proceed with the refund.",
                choices=["yes, process refund", "no, I want to wait a bit longer"],
                required=True,
            ),
        ],
    )


@agent.on_task_complete("lost_package_claim")
def on_done(call: guava.Call) -> None:
    tracking_number = call.get_field("tracking_number")
    request_refund = call.get_field("request_refund")
    package_description = call.get_field("package_description")
    checked_locations = call.get_field("checked_locations")

    tracker = _get_tracker(tracking_number)
    status = tracker.get("status") if tracker else None

    refund_result = None
    refund_attempted = False

    if request_refund == "yes, process refund":
        shipment = _get_shipment_by_tracking(tracking_number)
        if shipment:
            refund_result = _refund_shipment(shipment["id"])
            refund_attempted = True

    if not tracker:
        call.hangup(
            final_instructions=(
                f"Tell the customer you could not locate a shipment with tracking number '{tracking_number}'. "
                "Apologize and ask them to verify the number from their confirmation email, or offer to escalate to a human agent. "
                "Be empathetic and professional."
            )
        )
        return

    if status != "delivered":
        call.hangup(
            final_instructions=(
                f"Tell the customer their package with tracking number '{tracking_number}' does not yet show as delivered — "
                f"the current status is '{status}'. "
                "Encourage them to check again in 24 hours, and let them know they can call back if it still hasn't arrived. "
                "Be kind and reassuring."
            )
        )
        return

    if refund_attempted and refund_result:
        call.hangup(
            final_instructions=(
                f"Tell the customer their package (tracking: {tracking_number}) showed as delivered but was not received. "
                "Let them know you have successfully processed a shipping label refund on their behalf. "
                f"Their package contained: {package_description}. "
                "Advise them to also file a claim with their carrier and check with neighbors if they haven't already. "
                "Provide a case reference and wish them well. Be warm and sincere."
            )
        )
    elif refund_attempted and not refund_result:
        call.hangup(
            final_instructions=(
                f"Tell the customer their package (tracking: {tracking_number}) did show as delivered but was not received. "
                "Unfortunately, the refund could not be processed automatically. "
                "Let them know a support agent will follow up within one business day to complete the refund manually. "
                "Apologize for the inconvenience and be empathetic."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Tell the customer their package (tracking: {tracking_number}) shows as delivered. "
                "Since they've chosen to wait before requesting a refund, encourage them to check with neighbors and their building's mail room. "
                "Let them know they can call back anytime if the package doesn't turn up. "
                "Be helpful and understanding."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
