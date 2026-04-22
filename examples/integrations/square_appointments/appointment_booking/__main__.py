import guava
import os
import logging
from guava import logging_utils
import uuid
import requests
from datetime import datetime, timedelta, timezone


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


def search_customer_by_email(email: str) -> dict | None:
    """Search for an existing Square customer by email address."""
    resp = requests.post(
        f"{BASE_URL}/customers/search",
        headers=HEADERS,
        json={"query": {"filter": {"email_address": {"exact": email}}}},
        timeout=10,
    )
    resp.raise_for_status()
    customers = resp.json().get("customers", [])
    return customers[0] if customers else None


def create_customer(given_name: str, family_name: str, email: str, phone: str) -> dict:
    """Create a new Square customer record."""
    resp = requests.post(
        f"{BASE_URL}/customers",
        headers=HEADERS,
        json={
            "given_name": given_name,
            "family_name": family_name,
            "email_address": email,
            "phone_number": phone,
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["customer"]


def create_booking(customer_id: str, start_at: str, customer_note: str) -> dict:
    """Create a Square booking for the customer."""
    resp = requests.post(
        f"{BASE_URL}/bookings",
        headers=HEADERS,
        json={
            "idempotency_key": str(uuid.uuid4()),
            "booking": {
                "location_id": LOCATION_ID,
                "customer_id": customer_id,
                "customer_note": customer_note,
                "start_at": start_at,
                "appointment_segments": [
                    {
                        "duration_minutes": 60,
                        "service_variation_id": SERVICE_VARIATION_ID,
                        "team_member_id": TEAM_MEMBER_ID,
                    }
                ],
            },
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["booking"]


def build_start_at(preferred_date: str, preferred_time: str) -> str:
    """Construct a best-effort ISO 8601 timestamp from freeform date + time-of-day preference.

    In production, preferred_date should be resolved against POST /bookings/availability/search
    to find an actual open slot. Here we map time-of-day to a fixed hour as a placeholder.
    """
    hour_map = {
        "morning": 9,
        "afternoon": 14,
        "evening": 16,
    }
    hour = hour_map.get((preferred_time or "").lower(), 9)

    # Try to parse the date the caller provided; fall back to tomorrow if unparseable.
    for fmt in ("%B %d", "%B %dst", "%B %dnd", "%B %drd", "%B %dth", "%m/%d", "%m/%d/%Y", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(preferred_date.strip(), fmt)
            now = datetime.now(timezone.utc)
            year = now.year if parsed.month >= now.month else now.year + 1
            dt = datetime(year, parsed.month, parsed.day, hour, 0, 0, tzinfo=timezone.utc)
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        except (ValueError, AttributeError):
            continue

    # Fallback: tomorrow at the chosen hour
    tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
    dt = tomorrow.replace(hour=hour, minute=0, second=0, microsecond=0)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class AppointmentBookingController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Crestwood Wellness",
            agent_name="Jordan",
            agent_purpose="to help Crestwood Wellness clients book appointments",
        )

        self.set_task(
            objective=(
                "A client has called to book an appointment at Crestwood Wellness. "
                "Collect their contact details and preferences, then confirm their booking."
            ),
            checklist=[
                guava.Say(
                    "Thank you for calling Crestwood Wellness. This is Jordan. "
                    "I'd be happy to help you book an appointment today."
                ),
                guava.Field(
                    key="customer_name",
                    field_type="text",
                    description="Ask for the caller's full name — first and last.",
                    required=True,
                ),
                guava.Field(
                    key="customer_email",
                    field_type="text",
                    description="Ask for the caller's email address.",
                    required=True,
                ),
                guava.Field(
                    key="customer_phone",
                    field_type="text",
                    description="Ask for the best phone number to reach them.",
                    required=True,
                ),
                guava.Field(
                    key="service_type",
                    field_type="multiple_choice",
                    description="Ask which service they'd like to book.",
                    choices=["massage", "facial", "personal-training", "nutrition-consult", "other"],
                    required=True,
                ),
                guava.Field(
                    key="preferred_date",
                    field_type="text",
                    description="What date works best for you? Ask for a specific date.",
                    required=True,
                ),
                guava.Field(
                    key="preferred_time",
                    field_type="multiple_choice",
                    description="Ask whether they prefer a morning, afternoon, or evening appointment.",
                    choices=["morning", "afternoon", "evening"],
                    required=True,
                ),
                guava.Field(
                    key="special_requests",
                    field_type="text",
                    description="Ask if they have any special requests or notes for their appointment.",
                    required=False,
                ),
            ],
            on_complete=self.handle_complete,
        )

        self.accept_call()

    def handle_complete(self):
        customer_name = (self.get_field("customer_name") or "").strip()
        customer_email = (self.get_field("customer_email") or "").strip().lower()
        customer_phone = (self.get_field("customer_phone") or "").strip()
        service_type = self.get_field("service_type") or "appointment"
        preferred_date = self.get_field("preferred_date") or ""
        preferred_time = self.get_field("preferred_time") or "morning"
        special_requests = self.get_field("special_requests") or ""

        # Split name into given / family
        parts = customer_name.split(" ", 1)
        given_name = parts[0]
        family_name = parts[1] if len(parts) > 1 else ""

        logging.info(
            "Booking appointment for %s (%s), service=%s, date=%s, time=%s",
            customer_name, customer_email, service_type, preferred_date, preferred_time,
        )

        # Look up or create the customer
        customer = None
        try:
            customer = search_customer_by_email(customer_email)
            if customer:
                logging.info("Found existing customer: %s", customer.get("id"))
            else:
                customer = create_customer(given_name, family_name, customer_email, customer_phone)
                logging.info("Created new customer: %s", customer.get("id"))
        except Exception as e:
            logging.error("Customer lookup/creation failed: %s", e)

        if not customer:
            self.hangup(
                final_instructions=(
                    f"Apologize to {customer_name} — there was a problem creating their customer record. "
                    "Ask them to call back or visit us in person to complete the booking. Be warm and apologetic."
                )
            )
            return

        customer_id = customer["id"]
        start_at = build_start_at(preferred_date, preferred_time)

        customer_note = f"Service: {service_type}"
        if special_requests:
            customer_note += f". Notes: {special_requests}"

        booking = None
        try:
            booking = create_booking(customer_id, start_at, customer_note)
            logging.info("Booking created: %s, status=%s", booking.get("id"), booking.get("status"))
        except Exception as e:
            logging.error("Booking creation failed: %s", e)

        if not booking:
            self.hangup(
                final_instructions=(
                    f"Apologize to {customer_name} — we were unable to complete the booking at this time. "
                    "Ask them to try calling back in a few minutes or visit CreswoodWellness.com to book online."
                )
            )
            return

        booking_id = booking.get("id", "unknown")
        # Format the start_at for reading aloud
        try:
            dt = datetime.fromisoformat(start_at.replace("Z", "+00:00"))
            readable_time = dt.strftime("%A, %B %-d at %-I:%M %p")
        except (ValueError, AttributeError):
            readable_time = start_at

        self.hangup(
            final_instructions=(
                f"Let {customer_name} know their {service_type} appointment has been booked for "
                f"{readable_time}. Their booking confirmation ID is {booking_id} — "
                "read it out slowly so they can write it down. "
                "Let them know they'll receive a confirmation email shortly. "
                "Thank them for choosing Crestwood Wellness and wish them a wonderful day."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=AppointmentBookingController,
    )
