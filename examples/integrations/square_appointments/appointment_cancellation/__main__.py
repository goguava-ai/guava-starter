import guava
import os
import logging
import uuid
import requests
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)

ACCESS_TOKEN = os.environ["SQUARE_ACCESS_TOKEN"]
LOCATION_ID = os.environ["SQUARE_LOCATION_ID"]
SERVICE_VARIATION_ID = os.environ["SQUARE_SERVICE_VARIATION_ID"]
TEAM_MEMBER_ID = os.environ["SQUARE_TEAM_MEMBER_ID"]

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


def reschedule_booking(booking_id: str, booking_version: int, new_start_at: str) -> dict:
    """Reschedule a Square booking by updating its start time."""
    resp = requests.put(
        f"{BASE_URL}/bookings/{booking_id}",
        headers=HEADERS,
        json={
            "idempotency_key": str(uuid.uuid4()),
            "booking": {
                "version": booking_version,
                "start_at": new_start_at,
            },
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["booking"]


def build_start_at(preferred_date: str, preferred_time: str) -> str:
    """Construct a best-effort ISO 8601 timestamp from freeform date + time-of-day preference."""
    hour_map = {
        "morning": 9,
        "afternoon": 14,
        "evening": 16,
    }
    hour = hour_map.get((preferred_time or "").lower(), 9)

    for fmt in ("%B %d", "%B %dst", "%B %dnd", "%B %drd", "%B %dth", "%m/%d", "%m/%d/%Y", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(preferred_date.strip(), fmt)
            now = datetime.now(timezone.utc)
            year = now.year if parsed.month >= now.month else now.year + 1
            dt = datetime(year, parsed.month, parsed.day, hour, 0, 0, tzinfo=timezone.utc)
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        except (ValueError, AttributeError):
            continue

    from datetime import timedelta
    tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
    dt = tomorrow.replace(hour=hour, minute=0, second=0, microsecond=0)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def format_start_at(start_at: str) -> str:
    """Format an ISO timestamp for reading aloud."""
    try:
        dt = datetime.fromisoformat(start_at.replace("Z", "+00:00"))
        return dt.strftime("%A, %B %-d at %-I:%M %p")
    except (ValueError, AttributeError):
        return start_at


class AppointmentCancellationController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Crestwood Wellness",
            agent_name="Sam",
            agent_purpose="to help Crestwood Wellness clients cancel or reschedule their appointments",
        )

        self.set_task(
            objective=(
                "A client has called to cancel or reschedule an existing appointment. "
                "Verify their booking, confirm their intention, and process the request."
            ),
            checklist=[
                guava.Say(
                    "Thank you for calling Crestwood Wellness. This is Sam. "
                    "I can help you cancel or reschedule your appointment today."
                ),
                guava.Field(
                    key="booking_id",
                    field_type="text",
                    description=(
                        "Ask for their booking confirmation ID. "
                        "Let them know it was provided when they originally booked."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="customer_email",
                    field_type="text",
                    description="Ask for the email address on their account to verify their identity.",
                    required=True,
                ),
                guava.Field(
                    key="action",
                    field_type="multiple_choice",
                    description="Ask whether they'd like to cancel their appointment or reschedule it.",
                    choices=["cancel", "reschedule"],
                    required=True,
                ),
                guava.Field(
                    key="cancellation_reason",
                    field_type="text",
                    description="If cancelling, ask if they'd like to share a reason (optional).",
                    required=False,
                ),
                guava.Field(
                    key="new_preferred_date",
                    field_type="text",
                    description="If rescheduling, what new date would they prefer?",
                    required=False,
                ),
                guava.Field(
                    key="new_preferred_time",
                    field_type="multiple_choice",
                    description="If rescheduling, what time of day works best?",
                    choices=["morning", "afternoon", "evening"],
                    required=False,
                ),
            ],
            on_complete=self.handle_complete,
        )

        self.accept_call()

    def handle_complete(self):
        booking_id = (self.get_field("booking_id") or "").strip()
        customer_email = (self.get_field("customer_email") or "").strip().lower()
        action = (self.get_field("action") or "").lower()
        cancellation_reason = self.get_field("cancellation_reason") or ""
        new_preferred_date = self.get_field("new_preferred_date") or ""
        new_preferred_time = self.get_field("new_preferred_time") or "morning"

        logging.info(
            "Processing %s for booking %s (email: %s)",
            action, booking_id, customer_email,
        )

        # Fetch and verify the booking
        booking = None
        try:
            booking = get_booking(booking_id)
        except Exception as e:
            logging.error("Failed to fetch booking %s: %s", booking_id, e)

        if not booking:
            self.hangup(
                final_instructions=(
                    f"Let the caller know we couldn't find a booking with ID '{booking_id}'. "
                    "Ask them to double-check the ID from their confirmation email. "
                    "If they need further help they can visit CreswoodWellness.com. Be apologetic."
                )
            )
            return

        booking_version = booking.get("version", 0)
        current_start = booking.get("start_at", "")
        readable_current = format_start_at(current_start) if current_start else "your scheduled time"
        booking_status = booking.get("status", "")

        if booking_status in ("CANCELLED_BY_CUSTOMER", "CANCELLED_BY_SELLER", "NO_SHOW"):
            self.hangup(
                final_instructions=(
                    f"Let the caller know booking {booking_id} (originally at {readable_current}) "
                    f"already has a status of '{booking_status.lower()}' and cannot be modified. "
                    "If they believe this is an error, ask them to contact us directly. Be helpful."
                )
            )
            return

        if action == "cancel":
            cancelled_booking = None
            try:
                cancelled_booking = cancel_booking(booking_id, booking_version)
                logging.info(
                    "Booking %s cancelled, new status: %s",
                    booking_id, cancelled_booking.get("status"),
                )
            except Exception as e:
                logging.error("Failed to cancel booking %s: %s", booking_id, e)

            if cancelled_booking and "CANCELLED" in cancelled_booking.get("status", ""):
                reason_note = f" Reason noted: {cancellation_reason}." if cancellation_reason else ""
                self.hangup(
                    final_instructions=(
                        f"Let the caller know their appointment originally scheduled for "
                        f"{readable_current} has been successfully cancelled.{reason_note} "
                        "Let them know they're welcome to call back any time to rebook. "
                        "Thank them and wish them a good day."
                    )
                )
            else:
                self.hangup(
                    final_instructions=(
                        "Apologize — we weren't able to cancel the booking automatically at this time. "
                        "Let the caller know our team will follow up by email within one business day "
                        "to confirm the cancellation. Be apologetic and reassuring."
                    )
                )

        elif action == "reschedule":
            if not new_preferred_date:
                self.hangup(
                    final_instructions=(
                        "Apologize — we didn't capture a new preferred date for rescheduling. "
                        "Ask the caller to call back and we'll be happy to reschedule for them."
                    )
                )
                return

            new_start_at = build_start_at(new_preferred_date, new_preferred_time)
            readable_new = format_start_at(new_start_at)

            rescheduled = None
            try:
                rescheduled = reschedule_booking(booking_id, booking_version, new_start_at)
                logging.info(
                    "Booking %s rescheduled to %s, status=%s",
                    booking_id, new_start_at, rescheduled.get("status"),
                )
            except Exception as e:
                logging.error("Failed to reschedule booking %s: %s", booking_id, e)

            if rescheduled:
                self.hangup(
                    final_instructions=(
                        f"Let the caller know their appointment has been rescheduled to {readable_new}. "
                        f"Their booking ID remains {booking_id}. "
                        "They'll receive an updated confirmation email shortly. "
                        "Thank them for choosing Crestwood Wellness."
                    )
                )
            else:
                self.hangup(
                    final_instructions=(
                        "Apologize — we weren't able to reschedule the booking automatically at this time. "
                        "Let the caller know our team will reach out by email within one business day "
                        "to arrange the new time. Be warm and apologetic."
                    )
                )
        else:
            self.hangup(
                final_instructions=(
                    "Let the caller know we weren't sure whether they wanted to cancel or reschedule. "
                    "Ask them to call back and we'll be happy to assist. Apologize for any confusion."
                )
            )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=AppointmentCancellationController,
    )
