import guava
import os
import logging
from guava import logging_utils
import argparse
import uuid
import requests
from datetime import datetime, timezone


ACCESS_TOKEN = os.environ["SQUARE_ACCESS_TOKEN"]
LOCATION_ID = os.environ["SQUARE_LOCATION_ID"]

HEADERS = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json",
    "Square-Version": "2024-01-17",
}
BASE_URL = "https://connect.squareup.com/v2"


def get_booking(booking_id: str) -> dict | None:
    """Fetch a booking by ID from Square."""
    resp = requests.get(
        f"{BASE_URL}/bookings/{booking_id}",
        headers=HEADERS,
        timeout=10,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json().get("booking")


def cancel_booking(booking_id: str, booking_version: int) -> dict:
    """Cancel a Square booking."""
    resp = requests.post(
        f"{BASE_URL}/bookings/{booking_id}/cancel",
        headers=HEADERS,
        json={
            "booking_version": booking_version,
            "idempotency_key": str(uuid.uuid4()),
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["booking"]


def format_start_at(start_at: str) -> str:
    """Format an ISO timestamp for reading aloud."""
    try:
        dt = datetime.fromisoformat(start_at.replace("Z", "+00:00"))
        return dt.strftime("%A, %B %-d at %-I:%M %p")
    except (ValueError, AttributeError):
        return start_at


agent = guava.Agent(
    name="Morgan",
    organization="Crestwood Wellness",
    purpose="to remind Crestwood Wellness clients of their upcoming appointments",
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    booking_id = call.get_variable("booking_id")
    customer_name = call.get_variable("customer_name")

    # Pre-call: fetch appointment details
    booking = None
    readable_start = "your upcoming appointment"
    service_description = "your appointment"

    try:
        booking = get_booking(booking_id)
        if booking:
            start_at = booking.get("start_at", "")
            if start_at:
                readable_start = format_start_at(start_at)
            segments = booking.get("appointment_segments", [])
            if segments:
                duration = segments[0].get("duration_minutes", 60)
                service_description = f"your {duration}-minute appointment"
            logging.info(
                "Loaded booking %s: start=%s, status=%s",
                booking_id, start_at, booking.get("status"),
            )
        else:
            logging.warning("Booking %s not found for reminder call.", booking_id)
    except Exception as e:
        logging.error("Failed to fetch booking %s: %s", booking_id, e)

    call.set_variable("booking", booking)
    call.set_variable("readable_start", readable_start)
    call.set_variable("service_description", service_description)

    call.reach_person(contact_full_name=customer_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    booking_id = call.get_variable("booking_id")
    customer_name = call.get_variable("customer_name")

    service_description = call.get_variable("service_description")
    readable_start = call.get_variable("readable_start")

    if outcome == "unavailable":
        logging.info(
            "Unable to reach %s for appointment reminder (booking %s).",
            customer_name, booking_id,
        )
        call.hangup(
            final_instructions=(
                f"Leave a brief, friendly voicemail for {customer_name} from Crestwood Wellness. "
                f"Let them know you're calling as a reminder about {service_description} on "
                f"{readable_start}. Ask them to call back at their earliest convenience "
                "if they need to make any changes. Keep the message concise and professional."
            )
        )
    elif outcome == "available":
        call.set_task(
            "save_results",
            objective=(
                f"Remind {customer_name} of {service_description} at Crestwood Wellness "
                f"scheduled for {readable_start}. Confirm whether they'll be attending, "
                "and handle any cancellation or reschedule requests."
            ),
            checklist=[
                guava.Say(
                    f"Hi {customer_name}, this is Morgan calling from Crestwood Wellness. "
                    f"I'm reaching out as a friendly reminder about {service_description} "
                    f"we have scheduled for you on {readable_start}."
                ),
                guava.Field(
                    key="confirmation",
                    field_type="multiple_choice",
                    description=(
                        "Ask if they're still planning to come in. "
                        "Are they confirmed, do they need to cancel, or would they like to reschedule?"
                    ),
                    choices=["confirmed", "need-to-cancel", "need-to-reschedule"],
                    required=True,
                ),
                guava.Field(
                    key="has_questions",
                    field_type="multiple_choice",
                    description="Ask if they have any questions before their appointment.",
                    choices=["yes", "no"],
                    required=True,
                ),
                guava.Field(
                    key="special_requests",
                    field_type="text",
                    description="If they have questions or special requests, collect the details.",
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("save_results")
def save_results(call: guava.Call) -> None:
    booking_id = call.get_variable("booking_id")
    customer_name = call.get_variable("customer_name")
    readable_start = call.get_variable("readable_start")
    confirmation = call.get_field("confirmation") or ""
    has_questions = call.get_field("has_questions") or "no"
    special_requests = call.get_field("special_requests") or ""

    logging.info(
        "Reminder outcome for booking %s (%s): confirmation=%s, questions=%s",
        booking_id, customer_name, confirmation, has_questions,
    )

    if confirmation == "need-to-cancel":
        cancelled = None
        booking = call.get_variable("booking")
        if booking:
            try:
                booking_version = booking.get("version", 0)
                cancelled = cancel_booking(booking_id, booking_version)
                logging.info(
                    "Booking %s cancelled via reminder call, status=%s",
                    booking_id, cancelled.get("status"),
                )
            except Exception as e:
                logging.error("Failed to cancel booking %s during reminder: %s", booking_id, e)

        if cancelled and "CANCELLED" in cancelled.get("status", ""):
            call.hangup(
                final_instructions=(
                    f"Let {customer_name} know their appointment on {readable_start} "
                    "has been cancelled. Let them know they're welcome to call back any time to rebook. "
                    "Thank them and wish them a great day."
                )
            )
        else:
            call.hangup(
                final_instructions=(
                    f"Let {customer_name} know you've noted their wish to cancel the appointment "
                    f"on {readable_start}. Let them know our team will follow up to confirm "
                    "the cancellation by email. Thank them for letting us know."
                )
            )

    elif confirmation == "need-to-reschedule":
        call.hangup(
            final_instructions=(
                f"Let {customer_name} know you've noted they need to reschedule from {readable_start}. "
                "Ask them to call us back at their convenience or visit CreswoodWellness.com "
                "to pick a new time. Thank them and wish them a great day."
            )
        )

    else:
        # Confirmed — wrap up
        questions_note = ""
        if has_questions == "yes" and special_requests:
            questions_note = (
                f" Also let them know you've noted their request: '{special_requests}' "
                "and that their provider will be informed."
            )

        call.hangup(
            final_instructions=(
                f"Thank {customer_name} for confirming their appointment on {readable_start} "
                f"at Crestwood Wellness.{questions_note} "
                "Let them know we look forward to seeing them and wish them a wonderful day."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(description="Outbound appointment reminder call from Crestwood Wellness.")
    parser.add_argument("phone", help="Customer phone number (E.164 format, e.g. +15551234567)")
    parser.add_argument("--booking-id", required=True, help="Square booking ID")
    parser.add_argument("--name", required=True, help="Customer's full name")
    args = parser.parse_args()

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "booking_id": args.booking_id,
            "customer_name": args.name,
        },
    )
