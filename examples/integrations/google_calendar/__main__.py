import guava
import os
import logging
from guava import logging_utils
import datetime

import pickle

from google import genai as google_genai
from google.oauth2 import service_account
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from guava.helpers.genai import DatetimeFilter


SCOPES = ["https://www.googleapis.com/auth/calendar"]

_datetime_filter: DatetimeFilter | None = None
_calendar_service = None
_calendar_id: str = ""

APPOINTMENT_DURATION_MINS = int(os.environ.get("APPOINTMENT_DURATION_MINS", 30))
BOOKING_WINDOW_DAYS = int(os.environ.get("BOOKING_WINDOW_DAYS", 14))
BUSINESS_HOURS_START = int(os.environ.get("BUSINESS_HOURS_START", 9))
BUSINESS_HOURS_END = int(os.environ.get("BUSINESS_HOURS_END", 17))

# Set AUTH_MODE=oauth to use a saved OAuth token (token.pkl) instead of a
# service account. Run authorize.py once to generate the token file.
AUTH_MODE = os.environ.get("AUTH_MODE", "service_account")


def build_calendar_service():
    if AUTH_MODE == "oauth":
        with open("token.pkl", "rb") as f:
            creds = pickle.load(f)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
    else:
        creds = service_account.Credentials.from_service_account_file(
            os.environ["GOOGLE_CREDENTIALS_FILE"],
            scopes=SCOPES,
        )
    return build("calendar", "v3", credentials=creds)


def get_free_slots(service, calendar_id: str) -> list[str]:
    """
    Returns ISO-8601 datetime strings for every open appointment slot
    within the booking window, constrained to business hours.
    """
    tz = datetime.timezone.utc
    now = datetime.datetime.now(tz)
    window_end = now + datetime.timedelta(days=BOOKING_WINDOW_DAYS)

    # Query the freebusy API for the full window in one call.
    body = {
        "timeMin": now.isoformat(),
        "timeMax": window_end.isoformat(),
        "items": [{"id": calendar_id}],
    }
    result = service.freebusy().query(body=body).execute()
    busy_periods = result["calendars"][calendar_id]["busy"]

    busy_ranges = [
        (
            datetime.datetime.fromisoformat(p["start"]),
            datetime.datetime.fromisoformat(p["end"]),
        )
        for p in busy_periods
    ]

    def is_free(slot_start: datetime.datetime) -> bool:
        slot_end = slot_start + datetime.timedelta(minutes=APPOINTMENT_DURATION_MINS)
        for busy_start, busy_end in busy_ranges:
            if slot_start < busy_end and slot_end > busy_start:
                return False
        return True

    free_slots = []
    current_day = now.date() + datetime.timedelta(days=1)
    end_day = window_end.date()

    while current_day <= end_day:
        slot_time = datetime.datetime.combine(
            current_day,
            datetime.time(BUSINESS_HOURS_START, 0),
            tzinfo=tz,
        )
        day_end = datetime.datetime.combine(
            current_day,
            datetime.time(BUSINESS_HOURS_END, 0),
            tzinfo=tz,
        )
        while slot_time + datetime.timedelta(minutes=APPOINTMENT_DURATION_MINS) <= day_end:
            if is_free(slot_time):
                free_slots.append(slot_time.isoformat())
            slot_time += datetime.timedelta(minutes=APPOINTMENT_DURATION_MINS)
        current_day += datetime.timedelta(days=1)

    logging.info("Found %d free slots over the next %d days", len(free_slots), BOOKING_WINDOW_DAYS)
    return free_slots


def book_slot(service, calendar_id: str, iso_slot: str, caller_name: str) -> str:
    """Creates a calendar event for the given ISO-8601 slot. Returns the event link."""
    start = datetime.datetime.fromisoformat(iso_slot)
    end = start + datetime.timedelta(minutes=APPOINTMENT_DURATION_MINS)

    event = {
        "summary": f"Consultation — {caller_name}",
        "description": f"Booked by Guava voice agent for {caller_name}.",
        "start": {"dateTime": start.isoformat(), "timeZone": "UTC"},
        "end": {"dateTime": end.isoformat(), "timeZone": "UTC"},
    }
    created = service.events().insert(calendarId=calendar_id, body=event).execute()
    event_link = created.get("htmlLink", "")
    logging.info("Calendar event created: %s", event_link)
    return event_link


agent = guava.Agent(
    name="Grace",
    organization="Acme Consulting",
    purpose="to help callers book a consultation appointment",
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    global _datetime_filter, _calendar_service, _calendar_id
    _calendar_id = os.environ["GOOGLE_CALENDAR_ID"]
    _calendar_service = build_calendar_service()

    # Fetch free slots once at call start and build a DatetimeFilter over them.
    # The filter uses Gemini to match natural language queries (e.g. "Tuesday morning")
    # against the ISO-8601 slot list without a round-trip per utterance.
    free_slots = get_free_slots(_calendar_service, _calendar_id)
    _datetime_filter = DatetimeFilter(
        source_list=free_slots,
        client=google_genai.Client(),
    )

    call.set_task(
        "finalize_booking",
        objective="Book a consultation appointment for the caller.",
        checklist=[
            guava.Say(
                "Thank you for calling Acme Consulting. My name is Grace. "
                "I'd be happy to help you schedule a consultation."
            ),
            guava.Field(
                key="caller_name",
                field_type="text",
                description="Ask the caller for their full name.",
                required=True,
            ),
            # calendar_slot presents available times conversationally and lets
            # the caller express a preference in natural language (e.g. "next
            # Tuesday afternoon"). on_search_query is called with the caller's
            # preference string and returns (matching_slots, fallback_slots).
            guava.Field(
                key="appointment_time",
                field_type="calendar_slot",
                description=(
                    "Find an appointment time that works for the caller. "
                    f"Each slot is {APPOINTMENT_DURATION_MINS} minutes long."
                ),
                searchable=True,
                required=True,
            ),
            guava.Say(
                "Your appointment has been confirmed. "
                "You will receive a calendar invitation shortly. Have a great day!"
            ),
        ],
    )


@agent.on_search_query("appointment_time")
def search_appointment_time(call: guava.Call, query: str):
    return _datetime_filter.filter(query, max_results=3) if _datetime_filter else []


@agent.on_task_complete("finalize_booking")
def on_done(call: guava.Call) -> None:
    caller_name = call.get_field("caller_name") or "Unknown Caller"
    slot = call.get_field("appointment_time")

    if not slot:
        logging.error("No appointment_time collected — cannot book.")
        call.hangup(
            final_instructions=(
                "Apologize for a technical issue and let the caller know someone "
                "from Acme Consulting will follow up by email to confirm their time."
            )
        )
        return

    logging.info("Booking slot %s for %s", slot, caller_name)
    book_slot(
        service=_calendar_service,
        calendar_id=_calendar_id,
        iso_slot=slot,
        caller_name=caller_name,
    )
    call.hangup()


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
