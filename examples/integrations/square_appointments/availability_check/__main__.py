import logging
import os
import uuid
from datetime import datetime, timedelta, timezone

import guava
import requests
from guava import logging_utils

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


def search_availability(start_at: str, end_at: str) -> list:
    """Search available booking slots within the given date range."""
    resp = requests.post(
        f"{BASE_URL}/bookings/availability/search",
        headers=HEADERS,
        json={
            "query": {
                "filter": {
                    "location_id": LOCATION_ID,
                    "segment_filters": [
                        {
                            "service_variation_id": SERVICE_VARIATION_ID,
                            "team_member_id_filter": {"any": [TEAM_MEMBER_ID]},
                        }
                    ],
                    "start_at_range": {
                        "start_at": start_at,
                        "end_at": end_at,
                    },
                }
            }
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("availabilities", [])


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


def create_customer(given_name: str, family_name: str, email: str) -> dict:
    """Create a new Square customer record."""
    resp = requests.post(
        f"{BASE_URL}/customers",
        headers=HEADERS,
        json={
            "given_name": given_name,
            "family_name": family_name,
            "email_address": email,
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["customer"]


def create_booking(customer_id: str, start_at: str) -> dict:
    """Create a Square booking for the customer at the given start time."""
    resp = requests.post(
        f"{BASE_URL}/bookings",
        headers=HEADERS,
        json={
            "idempotency_key": str(uuid.uuid4()),
            "booking": {
                "location_id": LOCATION_ID,
                "customer_id": customer_id,
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


def build_week_range(preferred_week: str) -> tuple[str, str]:
    """Construct a 7-day ISO date range from a freeform week description.

    Attempts to parse "next week", "week of March 10", "March 10-16", etc.
    Falls back to the upcoming 7 days if parsing fails.
    """
    now = datetime.now(timezone.utc)
    week_lower = (preferred_week or "").lower().strip()

    # Handle "next week" explicitly
    if "next week" in week_lower:
        days_until_monday = (7 - now.weekday()) % 7 or 7
        start = now + timedelta(days=days_until_monday)
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=6, hours=23, minutes=59, seconds=59)
        return start.strftime("%Y-%m-%dT%H:%M:%SZ"), end.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Try to find a month/day anchor in the string
    for fmt in ("%B %d", "%B %dst", "%B %dnd", "%B %drd", "%B %dth", "%m/%d", "%m/%d/%Y", "%Y-%m-%d"):
        for token in preferred_week.split():
            for end_token in ["", *preferred_week.split()]:
                try:
                    trial = token if not end_token else f"{token} {end_token}"
                    parsed = datetime.strptime(trial.strip(), fmt)
                    year = now.year if parsed.month >= now.month else now.year + 1
                    start = datetime(year, parsed.month, parsed.day, 0, 0, 0, tzinfo=timezone.utc)
                    end = start + timedelta(days=6, hours=23, minutes=59, seconds=59)
                    return start.strftime("%Y-%m-%dT%H:%M:%SZ"), end.strftime("%Y-%m-%dT%H:%M:%SZ")
                except (ValueError, AttributeError):
                    continue

    # Fallback: next 7 days starting tomorrow
    start = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=6, hours=23, minutes=59, seconds=59)
    return start.strftime("%Y-%m-%dT%H:%M:%SZ"), end.strftime("%Y-%m-%dT%H:%M:%SZ")


def filter_by_time_of_day(availabilities: list, preferred_time_of_day: str) -> list:
    """Filter availability slots by morning/afternoon/evening preference."""
    pref = (preferred_time_of_day or "flexible").lower()
    if pref == "flexible":
        return availabilities

    hour_ranges = {
        "morning": (6, 12),
        "afternoon": (12, 17),
        "evening": (17, 22),
    }
    low, high = hour_ranges.get(pref, (0, 24))

    filtered = []
    for slot in availabilities:
        start_at = slot.get("start_at", "")
        try:
            dt = datetime.fromisoformat(start_at.replace("Z", "+00:00"))
            if low <= dt.hour < high:
                filtered.append(slot)
        except (ValueError, AttributeError):
            filtered.append(slot)
    return filtered


def format_slot(slot: dict) -> str:
    """Format an availability slot for reading aloud."""
    start_at = slot.get("start_at", "")
    try:
        dt = datetime.fromisoformat(start_at.replace("Z", "+00:00"))
        return dt.strftime("%A, %B %-d at %-I:%M %p")
    except (ValueError, AttributeError):
        return start_at


agent = guava.Agent(
    name="Taylor",
    organization="Crestwood Wellness",
    purpose="to help Crestwood Wellness clients check available appointment slots",
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "check_availability",
        objective=(
            "A client has called to check what appointment slots are available at Crestwood Wellness. "
            "Collect their preferences, search for open slots, present options, and offer to book."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Crestwood Wellness. This is Taylor. "
                "I can help you check our available appointment times today."
            ),
            guava.Field(
                key="service_type",
                field_type="multiple_choice",
                description="Ask which service they're interested in.",
                choices=["massage", "facial", "personal-training", "nutrition-consult", "other"],
                required=True,
            ),
            guava.Field(
                key="preferred_week",
                field_type="text",
                description="Which week are you looking at? Ask for a specific week or date range.",
                required=True,
            ),
            guava.Field(
                key="preferred_time_of_day",
                field_type="multiple_choice",
                description="Do they have a preferred time of day, or are they flexible?",
                choices=["morning", "afternoon", "evening", "flexible"],
                required=True,
            ),
        ],
    )


@agent.on_task_complete("check_availability")
def check_availability(call: guava.Call) -> None:
    service_type = call.get_field("service_type") or "appointment"
    preferred_week = call.get_field("preferred_week") or ""
    preferred_time_of_day = call.get_field("preferred_time_of_day") or "flexible"

    logging.info(
        "Checking availability: service=%s, week=%s, time_of_day=%s",
        service_type, preferred_week, preferred_time_of_day,
    )

    start_at, end_at = build_week_range(preferred_week)

    availabilities = []
    try:
        availabilities = search_availability(start_at, end_at)
        logging.info("Found %d raw availability slots", len(availabilities))
    except Exception as e:
        logging.error("Availability search failed: %s", e)

    # Filter by time-of-day preference
    filtered = filter_by_time_of_day(availabilities, preferred_time_of_day)
    available_slots = filtered[:5]  # Keep up to 5 slots

    logging.info(
        "%d slots after filtering by time-of-day preference '%s'",
        len(available_slots), preferred_time_of_day,
    )

    if not available_slots:
        call.hangup(
            final_instructions=(
                f"Let the caller know we don't have any {service_type} openings matching their "
                f"preferences for the week of '{preferred_week}'. "
                "Suggest they try a different week or check CreswoodWellness.com for the full calendar. "
                "Be friendly and helpful."
            )
        )
        return

    slot_descriptions = [format_slot(s) for s in available_slots]
    slots_text = "; ".join(slot_descriptions)

    call.set_variable("available_slots", available_slots)

    # Ask if they want to book now
    call.set_task(
        "handle_booking_decision",
        objective=(
            f"You found {len(available_slots)} available {service_type} slot(s) for "
            f"the week of '{preferred_week}'. Present them naturally and ask if the caller wants to book."
        ),
        checklist=[
            guava.Say(
                f"Great news — I found some available times for a {service_type}. "
                f"Here are the open slots: {slots_text}. "
                "Do any of those work for you?"
            ),
            guava.Field(
                key="wants_to_book",
                field_type="multiple_choice",
                description="Ask if they'd like to go ahead and book one of these slots right now.",
                choices=["yes", "no"],
                required=True,
            ),
            guava.Field(
                key="chosen_slot",
                field_type="text",
                description="If yes, ask which slot they'd prefer (e.g., 'the Tuesday morning one').",
                required=False,
            ),
            guava.Field(
                key="booking_email",
                field_type="text",
                description="If booking, ask for their email address to look up their account.",
                required=False,
            ),
            guava.Field(
                key="booking_name",
                field_type="text",
                description="If booking and they're a new client, ask for their full name.",
                required=False,
            ),
        ],
    )


@agent.on_task_complete("handle_booking_decision")
def handle_booking_decision(call: guava.Call) -> None:
    wants_to_book = (call.get_field("wants_to_book") or "no").lower()
    chosen_slot_text = call.get_field("chosen_slot") or ""
    booking_email = (call.get_field("booking_email") or "").strip().lower()
    booking_name = (call.get_field("booking_name") or "").strip()

    if wants_to_book != "yes" or not booking_email:
        call.hangup(
            final_instructions=(
                "Let the caller know they can call back any time to book, or visit "
                "CreswoodWellness.com to schedule online. "
                "Thank them for checking availability and wish them a great day."
            )
        )
        return

    available_slots = call.get_variable("available_slots")

    # Pick the slot — try to match their text choice, otherwise use the first
    chosen = available_slots[0] if available_slots else None
    if chosen_slot_text and available_slots:
        chosen_text_lower = chosen_slot_text.lower()
        for slot in available_slots:
            label = format_slot(slot).lower()
            # Match on day name or time fragment
            for word in chosen_text_lower.split():
                if word in label:
                    chosen = slot
                    break

    if not chosen:
        call.hangup(
            final_instructions=(
                "Apologize — we weren't able to identify which slot they'd prefer. "
                "Ask them to call back or visit CreswoodWellness.com to complete the booking."
            )
        )
        return

    start_at = chosen.get("start_at", "")
    readable_slot = format_slot(chosen)

    logging.info(
        "Booking slot %s for %s (%s)", start_at, booking_name, booking_email,
    )

    # Look up or create customer
    customer = None
    try:
        customer = search_customer_by_email(booking_email)
        if customer:
            logging.info("Found existing customer: %s", customer.get("id"))
        else:
            parts = booking_name.split(" ", 1)
            given_name = parts[0]
            family_name = parts[1] if len(parts) > 1 else ""
            customer = create_customer(given_name, family_name, booking_email)
            logging.info("Created new customer: %s", customer.get("id"))
    except Exception as e:
        logging.error("Customer lookup/creation failed: %s", e)

    if not customer:
        call.hangup(
            final_instructions=(
                "Apologize — there was a problem retrieving the caller's account. "
                "Ask them to call back or book at CreswoodWellness.com. Be warm and apologetic."
            )
        )
        return

    booking = None
    try:
        booking = create_booking(customer["id"], start_at)
        logging.info(
            "Booking created: %s, status=%s", booking.get("id"), booking.get("status"),
        )
    except Exception as e:
        logging.error("Booking creation failed: %s", e)

    if booking:
        booking_id = booking.get("id", "unknown")
        call.hangup(
            final_instructions=(
                f"Let the caller know their appointment has been booked for {readable_slot}. "
                f"Their confirmation ID is {booking_id} — read it slowly so they can note it. "
                "They'll receive a confirmation email shortly. "
                "Thank them for choosing Crestwood Wellness and wish them a wonderful day."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Apologize — we were unable to complete the booking for {readable_slot} at this time. "
                "Ask them to try calling back in a few minutes or visit CreswoodWellness.com to book online."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
