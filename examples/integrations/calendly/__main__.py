import guava
import os
import logging
from guava import logging_utils
import requests
import datetime
import zoneinfo

from google import genai as google_genai

from guava.helpers.genai import DateRangeParser


CALENDLY_TOKEN = os.environ["CALENDLY_TOKEN"]
AGENT_NUMBER = os.environ["GUAVA_AGENT_NUMBER"]

HEADERS = {
    "Authorization": f"Bearer {CALENDLY_TOKEN}",
    "Content-Type": "application/json",
}

VALID_TIMEZONES = zoneinfo.available_timezones()


# ── Calendly API helpers ─────────────────────────────────────────────────────


def get_current_user_uri() -> str:
    resp = requests.get("https://api.calendly.com/users/me", headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.json()["resource"]["uri"]


def get_event_types(user_uri: str) -> list[dict]:
    resp = requests.get(
        "https://api.calendly.com/event_types",
        headers=HEADERS,
        params={"user": user_uri, "active": "true"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("collection", [])


def get_available_slots(
    event_type_uri: str,
    start_date: datetime.date,
    end_date: datetime.date,
) -> list[str]:
    """
    Returns ISO-8601 start times for open slots between start_date and end_date.
    Pages in 7-day chunks (Calendly API limit per request). Calendly only returns
    slots that respect the event type's configured booking window and minimum notice.
    """
    slots = []
    now = datetime.datetime.now(datetime.timezone.utc)

    # Calendly requires start_time to be in the future.
    earliest = now + datetime.timedelta(minutes=5)
    chunk_start = max(
        earliest,
        datetime.datetime.combine(start_date, datetime.time.min, tzinfo=datetime.timezone.utc),
    )
    window_end = datetime.datetime.combine(
        end_date + datetime.timedelta(days=1), datetime.time.min, tzinfo=datetime.timezone.utc,
    )

    while chunk_start < window_end:
        chunk_end = min(chunk_start + datetime.timedelta(days=7), window_end)

        resp = requests.get(
            "https://api.calendly.com/event_type_available_times",
            headers=HEADERS,
            params={
                "event_type": event_type_uri,
                "start_time": chunk_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "end_time": chunk_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
            timeout=10,
        )
        resp.raise_for_status()
        slots.extend(s["start_time"] for s in resp.json().get("collection", []))

        chunk_start = chunk_end

    logging.info("Found %d available slots between %s and %s", len(slots), start_date, end_date)
    return slots


def create_invitee(event_type: dict, start_time: str, name: str, email: str, timezone: str) -> dict:
    """
    Books the meeting via POST /invitees (requires a paid Calendly plan).
    Raises requests.HTTPError with status 403 on free-tier accounts.
    """
    if timezone not in VALID_TIMEZONES:
        logging.warning("Invalid timezone %r — falling back to UTC", timezone)
        timezone = "UTC"

    payload = {
        "event_type": event_type["uri"],
        "start_time": start_time,
        "invitee": {
            "name": name,
            "email": email,
            "timezone": timezone,
        },
    }

    locations = event_type.get("locations") or []
    if locations:
        payload["location"] = {"kind": locations[0]["kind"]}

    resp = requests.post(
        "https://api.calendly.com/invitees",
        headers=HEADERS,
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["resource"]


def create_scheduling_link(event_type_uri: str) -> str:
    """Creates a single-use scheduling link (fallback for free-tier accounts)."""
    resp = requests.post(
        "https://api.calendly.com/scheduling_links",
        headers=HEADERS,
        json={
            "max_event_count": 1,
            "owner": event_type_uri,
            "owner_type": "EventType",
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["resource"]["booking_url"]


def format_slot(iso_slot: str) -> str:
    """Formats an ISO-8601 slot into a human-readable string like 'April 07 at 04:00 PM UTC'."""
    dt = datetime.datetime.fromisoformat(iso_slot.replace("Z", "+00:00"))
    return dt.strftime("%B %d at %I:%M %p %Z")


# ── Call controller ──────────────────────────────────────────────────────────


class AppointmentSchedulingController(guava.CallController):
    def __init__(self):
        super().__init__()
        self.caller_number = None
        self.selected_event_type = None
        self.genai_client = google_genai.Client(vertexai=True, location="us-central1")
        self.date_parser = DateRangeParser(client=self.genai_client)

        user_uri = get_current_user_uri()
        event_types = get_event_types(user_uri)
        self.event_type_map = {et["name"]: et for et in event_types}

        self.set_persona(
            organization_name="Acme Consulting",
            agent_name="Grace",
            agent_purpose="to help callers book a meeting with the Acme Consulting team",
        )

        self.set_task(
            objective="Determine what kind of meeting the caller needs and collect their details.",
            checklist=[
                guava.Say(
                    "Thank you for calling Acme Consulting. My name is Grace. "
                    "I'd be happy to help you schedule a meeting."
                ),
                guava.Field(
                    key="caller_name",
                    field_type="text",
                    description="Ask the caller for their full name.",
                    required=True,
                ),
                guava.Field(
                    key="caller_email",
                    field_type="text",
                    description="Ask for their email address so we can send a confirmation.",
                    required=True,
                ),
                guava.Field(
                    key="caller_timezone",
                    field_type="text",
                    description=(
                        "Ask for their timezone. Capture as an IANA timezone string "
                        "such as 'America/New_York', 'America/Los_Angeles', or 'Europe/London'."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="meeting_type",
                    field_type="multiple_choice",
                    description=(
                        "Ask what kind of meeting they'd like to schedule and offer the options. "
                        "Match their answer to one of the choices."
                    ),
                    choices=list(self.event_type_map.keys()),
                    required=True,
                ),
            ],
            on_complete=self.start_slot_selection,
        )

        self.accept_call()

    def on_incoming_call(self, from_number):
        self.caller_number = from_number

    def start_slot_selection(self):
        """Set up the slot selection task after the caller picks a meeting type."""
        meeting_type = self.get_field("meeting_type")
        self.selected_event_type = self.event_type_map.get(meeting_type)

        if not self.selected_event_type:
            logging.error("Unknown meeting type: %s", meeting_type)
            self.hangup(
                final_instructions=(
                    "Apologize and let the caller know we had trouble finding that meeting type. "
                    "Ask them to call back or reach out by email."
                )
            )
            return

        caller_name = self.get_field("caller_name")
        self.set_task(
            objective=f"Find a {meeting_type} slot that works for {caller_name}.",
            checklist=[
                guava.Field(
                    key="appointment_time",
                    field_type="calendar_slot",
                    description=(
                        f"Ask when they'd like to schedule their {meeting_type} and offer "
                        "matching times. Propose 2–3 options and confirm their choice."
                    ),
                    choice_generator=self.filter_slots,
                    required=True,
                ),
                guava.Say(
                    "Your appointment is confirmed. "
                    "You'll receive a calendar invite and confirmation email shortly. "
                    "Have a great day!"
                ),
            ],
            on_complete=self.finalize_booking,
        )

    def filter_slots(self, query: str) -> tuple[list[str], list[str]]:
        """Fetch available slots from Calendly on demand based on the caller's request."""
        event_type_uri = self.selected_event_type["uri"]

        # Parse the caller's natural language into a date range (±1 day buffer).
        start, end = self.date_parser.parse(query, buffer_days=1)
        slots = get_available_slots(event_type_uri, start, end)
        print(slots)

        if slots:
            return slots, []

        # Nothing in that range — widen to ±3 extra days for alternatives.
        wide_start = start - datetime.timedelta(days=3)
        wide_end = end + datetime.timedelta(days=3)
        if wide_start < datetime.date.today():
            wide_start = datetime.date.today()

        wider_slots = get_available_slots(event_type_uri, wide_start, wide_end)
        return [], wider_slots

    def finalize_booking(self):
        """Book the meeting via the Calendly API, or send a scheduling link as fallback."""
        name = self.get_field("caller_name") or "Unknown Caller"
        email = self.get_field("caller_email")
        timezone = self.get_field("caller_timezone") or "UTC"
        slot = self.get_field("appointment_time")
        meeting_type = self.selected_event_type["name"]

        if not slot or not email:
            logging.error("Missing required booking fields — slot: %s, email: %s", slot, email)
            self.hangup(
                final_instructions=(
                    "Apologize for a technical issue and let the caller know someone from "
                    "Acme Consulting will follow up by email to confirm their appointment."
                )
            )
            return

        logging.info("Booking %s for %s (%s) at %s", meeting_type, name, email, slot)

        try:
            invitee = create_invitee(
                event_type=self.selected_event_type,
                start_time=slot,
                name=name,
                email=email,
                timezone=timezone,
            )
            logging.info("Booking confirmed:  %s", invitee.get("uri"))
            logging.info("Cancel URL:         %s", invitee.get("cancel_url"))
            logging.info("Reschedule URL:     %s", invitee.get("reschedule_url"))
            self.hangup()

        except requests.HTTPError as e:
            if e.response.status_code != 403:
                logging.error("Calendly API error: %s — %s", e, e.response.text)
                self.hangup(
                    final_instructions=(
                        "Apologize for a technical issue and let the caller know someone from "
                        "Acme Consulting will follow up by email to confirm their appointment."
                    )
                )
                return

            # Free-tier fallback: create a scheduling link and text it to the caller.
            logging.warning("Scheduling API unavailable (free tier) — falling back to scheduling link")
            booking_url = None
            try:
                booking_url = create_scheduling_link(self.selected_event_type["uri"])
                logging.info("Scheduling link created: %s", booking_url)
            except Exception as link_err:
                logging.error("Failed to create scheduling link: %s", link_err)

            sms_sent = False
            if booking_url and self.caller_number:
                try:
                    guava.Client().send_sms(
                        from_number=AGENT_NUMBER,
                        to_number=self.caller_number,
                        message=(
                            f"Hi {name}, your {meeting_type} is scheduled for "
                            f"{format_slot(slot)}. Complete your booking here: {booking_url}"
                        ),
                    )
                    logging.info("Booking link sent via SMS to %s", self.caller_number)
                    sms_sent = True
                except Exception as sms_err:
                    logging.error("Failed to send SMS: %s", sms_err)

            if sms_sent:
                self.hangup(
                    final_instructions=(
                        f"Let {name} know we weren't able to complete the booking automatically, "
                        "but we've sent a personal booking link to their phone via text message."
                    )
                )
            else:
                self.hangup(
                    final_instructions=(
                        f"Let {name} know we weren't able to complete the booking automatically. "
                        "Ask them to visit our website to complete their booking."
                    )
                )


if __name__ == "__main__":
    logging_utils.configure_logging()
    guava.Client().listen_inbound(
        agent_number=AGENT_NUMBER,
        controller_class=AppointmentSchedulingController,
    )
