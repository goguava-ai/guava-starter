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


class AppointmentReminderController(guava.CallController):
    def __init__(self, booking_id: str, customer_name: str):
        super().__init__()
        self.booking_id = booking_id
        self.customer_name = customer_name

        # Pre-call: fetch appointment details
        self.booking = None
        self.readable_start = "your upcoming appointment"
        self.service_description = "your appointment"

        try:
            self.booking = get_booking(booking_id)
            if self.booking:
                start_at = self.booking.get("start_at", "")
                if start_at:
                    self.readable_start = format_start_at(start_at)
                segments = self.booking.get("appointment_segments", [])
                if segments:
                    duration = segments[0].get("duration_minutes", 60)
                    self.service_description = f"your {duration}-minute appointment"
                logging.info(
                    "Loaded booking %s: start=%s, status=%s",
                    booking_id, start_at, self.booking.get("status"),
                )
            else:
                logging.warning("Booking %s not found for reminder call.", booking_id)
        except Exception as e:
            logging.error("Failed to fetch booking %s: %s", booking_id, e)

        self.set_persona(
            organization_name="Crestwood Wellness",
            agent_name="Morgan",
            agent_purpose="to remind Crestwood Wellness clients of their upcoming appointments",
        )

        self.reach_person(
            contact_full_name=customer_name,
            on_success=self.begin_call,
            on_failure=self.recipient_unavailable,
        )

    def begin_call(self):
        self.set_task(
            objective=(
                f"Remind {self.customer_name} of {self.service_description} at Crestwood Wellness "
                f"scheduled for {self.readable_start}. Confirm whether they'll be attending, "
                "and handle any cancellation or reschedule requests."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.customer_name}, this is Morgan calling from Crestwood Wellness. "
                    f"I'm reaching out as a friendly reminder about {self.service_description} "
                    f"we have scheduled for you on {self.readable_start}."
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
            on_complete=self.save_results,
        )

    def save_results(self):
        confirmation = self.get_field("confirmation") or ""
        has_questions = self.get_field("has_questions") or "no"
        special_requests = self.get_field("special_requests") or ""

        logging.info(
            "Reminder outcome for booking %s (%s): confirmation=%s, questions=%s",
            self.booking_id, self.customer_name, confirmation, has_questions,
        )

        if confirmation == "need-to-cancel":
            cancelled = None
            if self.booking:
                try:
                    booking_version = self.booking.get("version", 0)
                    cancelled = cancel_booking(self.booking_id, booking_version)
                    logging.info(
                        "Booking %s cancelled via reminder call, status=%s",
                        self.booking_id, cancelled.get("status"),
                    )
                except Exception as e:
                    logging.error("Failed to cancel booking %s during reminder: %s", self.booking_id, e)

            if cancelled and "CANCELLED" in cancelled.get("status", ""):
                self.hangup(
                    final_instructions=(
                        f"Let {self.customer_name} know their appointment on {self.readable_start} "
                        "has been cancelled. Let them know they're welcome to call back any time to rebook. "
                        "Thank them and wish them a great day."
                    )
                )
            else:
                self.hangup(
                    final_instructions=(
                        f"Let {self.customer_name} know you've noted their wish to cancel the appointment "
                        f"on {self.readable_start}. Let them know our team will follow up to confirm "
                        "the cancellation by email. Thank them for letting us know."
                    )
                )

        elif confirmation == "need-to-reschedule":
            self.hangup(
                final_instructions=(
                    f"Let {self.customer_name} know you've noted they need to reschedule from {self.readable_start}. "
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

            self.hangup(
                final_instructions=(
                    f"Thank {self.customer_name} for confirming their appointment on {self.readable_start} "
                    f"at Crestwood Wellness.{questions_note} "
                    "Let them know we look forward to seeing them and wish them a wonderful day."
                )
            )

    def recipient_unavailable(self):
        logging.info(
            "Unable to reach %s for appointment reminder (booking %s).",
            self.customer_name, self.booking_id,
        )
        self.hangup(
            final_instructions=(
                f"Leave a brief, friendly voicemail for {self.customer_name} from Crestwood Wellness. "
                f"Let them know you're calling as a reminder about {self.service_description} on "
                f"{self.readable_start}. Ask them to call back at their earliest convenience "
                "if they need to make any changes. Keep the message concise and professional."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(description="Outbound appointment reminder call from Crestwood Wellness.")
    parser.add_argument("phone", help="Customer phone number (E.164 format, e.g. +15551234567)")
    parser.add_argument("--booking-id", required=True, help="Square booking ID")
    parser.add_argument("--name", required=True, help="Customer's full name")
    args = parser.parse_args()

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=AppointmentReminderController(
            booking_id=args.booking_id,
            customer_name=args.name,
        ),
    )
