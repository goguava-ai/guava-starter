import logging
import os

import guava
import requests
from guava import logging_utils

AFTERSHIP_API_KEY = os.environ["AFTERSHIP_API_KEY"]
HEADERS = {
    "as-api-key": AFTERSHIP_API_KEY,
    "Content-Type": "application/json",
}
BASE_URL = "https://api.aftership.com/v4"

# Human-readable descriptions for AfterShip tracking status tags.
TAG_LABELS = {
    "Pending": "is still being processed — the carrier hasn't scanned it yet",
    "InfoReceived": "has been received by the carrier but not yet picked up",
    "InTransit": "is currently in transit",
    "OutForDelivery": "is out for delivery today",
    "AttemptFail": "had a failed delivery attempt — the carrier tried but couldn't deliver",
    "Delivered": "has been delivered",
    "AvailableForPickup": "is available for pickup at a carrier facility",
    "Exception": "has a carrier exception — something unexpected occurred",
    "Expired": "has expired with no further carrier updates",
}


def search_tracking(tracking_number: str) -> dict | None:
    """Find the most recent tracking record matching this number."""
    resp = requests.get(
        f"{BASE_URL}/trackings",
        headers=HEADERS,
        params={"keyword": tracking_number, "limit": 1},
        timeout=10,
    )
    resp.raise_for_status()
    items = resp.json().get("data", {}).get("trackings", [])
    return items[0] if items else None


def format_last_checkpoint(checkpoints: list) -> str:
    if not checkpoints:
        return ""
    last = checkpoints[0]
    message = last.get("message") or ""
    location = last.get("city") or last.get("country_name") or ""
    if message and location:
        return f"{message} ({location})"
    return message


agent = guava.Agent(
    name="Alex",
    organization="Meridian Commerce",
    purpose="to help Meridian Commerce customers check the current status of their shipments",
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "look_up_shipment",
        objective=(
            "A customer is calling to check on a shipment. Collect their tracking number "
            "and look up the current delivery status."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Meridian Commerce. This is Alex. "
                "I can look up your shipment status right away."
            ),
            guava.Field(
                key="tracking_number",
                field_type="text",
                description=(
                    "Ask the customer for their tracking number. "
                    "It's typically found in their shipping confirmation email or order page."
                ),
                required=True,
            ),
        ],
    )


@agent.on_task_complete("look_up_shipment")
def on_done(call: guava.Call) -> None:
    tracking_number = (call.get_field("tracking_number") or "").strip()
    logging.info("Looking up tracking number: %s", tracking_number)

    try:
        tracking = search_tracking(tracking_number)
    except Exception as e:
        logging.error("AfterShip lookup failed for %s: %s", tracking_number, e)
        tracking = None

    if not tracking:
        call.hangup(
            final_instructions=(
                "Let the customer know you weren't able to find a shipment with that tracking number. "
                "Suggest they double-check the number from their shipping confirmation email. "
                "Offer to transfer them to a support agent if they need further help."
            )
        )
        return

    tag = tracking.get("tag", "")
    status_text = TAG_LABELS.get(tag, "in an unknown status")
    carrier = (tracking.get("slug") or "").replace("-", " ").title()
    expected = (
        tracking.get("expected_delivery")
        or tracking.get("current_expected_delivery")
        or ""
    )
    checkpoints = tracking.get("checkpoints") or []
    last_update = format_last_checkpoint(checkpoints)

    logging.info("Tracking %s: tag=%s, carrier=%s", tracking_number, tag, carrier)

    eta_note = f" The estimated delivery date is {expected}." if expected else ""
    carrier_note = f" The carrier is {carrier}." if carrier else ""
    update_note = (
        f" The most recent carrier update was: '{last_update}'." if last_update else ""
    )

    escalation_note = ""
    if tag in ("AttemptFail", "Exception"):
        escalation_note = (
            " Since this requires carrier action, offer to provide the carrier's contact "
            "information or escalate to a support agent who can follow up directly."
        )

    call.hangup(
        final_instructions=(
            f"Let the customer know their shipment {status_text}.{carrier_note}"
            f"{eta_note}{update_note}{escalation_note} "
            "Be warm and helpful. Thank them for calling Meridian Commerce."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
