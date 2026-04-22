import argparse
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


def get_tracking(slug: str, tracking_number: str) -> dict | None:
    resp = requests.get(
        f"{BASE_URL}/trackings/{slug}/{tracking_number}",
        headers=HEADERS,
        timeout=10,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json().get("data", {}).get("tracking")


def add_tracking_note(slug: str, tracking_number: str, note: str) -> None:
    """Append a note to the tracking record via metadata update."""
    requests.put(
        f"{BASE_URL}/trackings/{slug}/{tracking_number}",
        headers=HEADERS,
        json={"tracking": {"note": note}},
        timeout=10,
    )


agent = guava.Agent(
    name="Alex",
    organization="Meridian Commerce",
    purpose=(
        "to notify Meridian Commerce customers about delivery exceptions "
        "on their shipments and help resolve them"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(contact_full_name=call.get_variable("customer_name"))


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    if outcome == "unavailable":
        logging.info(
            "Unable to reach %s for delivery exception on %s",
            call.get_variable("customer_name"), call.get_variable("tracking_number"),
        )
        call.hangup(
            final_instructions=(
                f"Leave a brief voicemail for {call.get_variable('customer_name')} from Meridian Commerce. "
                f"Let them know there is a delivery exception on tracking {call.get_variable('tracking_number')} "
                "and that they should check their email for details and next steps. "
                "Keep it short and professional."
            )
        )
    elif outcome == "available":
        customer_name = call.get_variable("customer_name")
        tracking_number = call.get_variable("tracking_number")
        slug = call.get_variable("slug")
        exception_message = call.get_variable("exception_message")
        carrier = slug.replace("-", " ").title()

        call.set_task(
            "deliver_exception_notification",
            objective=(
                f"Inform {customer_name} about a delivery exception on tracking "
                f"{tracking_number} and understand how they'd like to proceed."
            ),
            checklist=[
                guava.Say(
                    f"Hi {customer_name}, this is Alex calling from Meridian Commerce. "
                    f"I'm reaching out because there's been an update on your shipment "
                    f"with tracking number {tracking_number}. "
                    f"The {carrier} carrier has flagged an exception: {exception_message}. "
                    "I wanted to make sure you're aware and see how we can help."
                ),
                guava.Field(
                    key="resolution_preference",
                    field_type="multiple_choice",
                    description=(
                        "Ask how the customer would like to proceed. "
                        "Present the options clearly."
                    ),
                    choices=[
                        "redeliver to same address",
                        "pick up from carrier facility",
                        "update delivery address",
                        "cancel and refund",
                        "just keep me updated",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="additional_notes",
                    field_type="text",
                    description=(
                        "Ask if there's anything else they'd like us to know or pass along to the carrier."
                    ),
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("deliver_exception_notification")
def on_done(call: guava.Call) -> None:
    preference = call.get_field("resolution_preference") or "just keep me updated"
    notes = call.get_field("additional_notes") or ""
    customer_name = call.get_variable("customer_name")
    tracking_number = call.get_variable("tracking_number")
    slug = call.get_variable("slug")

    logging.info(
        "Exception resolution for tracking %s: preference=%s",
        tracking_number, preference,
    )

    note_text = f"Customer call outcome — preference: {preference}."
    if notes:
        note_text += f" Customer notes: {notes}"

    try:
        add_tracking_note(slug, tracking_number, note_text)
    except Exception as e:
        logging.warning("Failed to add note to tracking %s: %s", tracking_number, e)

    if preference == "cancel and refund":
        call.hangup(
            final_instructions=(
                f"Let {customer_name} know you've noted their request for a cancellation "
                "and refund, and that our support team will process it within one business day. "
                "They'll receive a confirmation email. Thank them for their patience."
            )
        )
    elif preference == "update delivery address":
        call.hangup(
            final_instructions=(
                f"Let {customer_name} know that updating the delivery address requires "
                "our support team to coordinate with the carrier, and that someone will "
                "follow up by email within a few hours to confirm the new address and next steps. "
                "Thank them for their patience."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {customer_name} for their time. Let them know you've noted "
                f"their preference — {preference} — and that our team will follow up by email "
                "with the next steps. Assure them we're working to get this resolved quickly."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound call to notify a customer of a delivery exception."
    )
    parser.add_argument("phone", help="Customer phone number (E.164, e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Customer full name")
    parser.add_argument("--tracking-number", required=True, help="Shipment tracking number")
    parser.add_argument("--slug", required=True, help="Carrier slug (e.g. ups, fedex, usps)")
    parser.add_argument(
        "--exception",
        default="a delivery exception has been flagged by the carrier",
        help="Description of the exception from AfterShip",
    )
    args = parser.parse_args()

    logging.info(
        "Calling %s (%s) about exception on tracking %s",
        args.name, args.phone, args.tracking_number,
    )

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "customer_name": args.name,
            "tracking_number": args.tracking_number,
            "slug": args.slug,
            "exception_message": args.exception,
        },
    )
