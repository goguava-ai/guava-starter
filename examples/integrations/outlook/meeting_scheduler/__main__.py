import guava
import os
import logging
from guava import logging_utils
import datetime
import requests
from guava.helpers.genai import DatetimeFilter


GRAPH_ACCESS_TOKEN = os.environ["GRAPH_ACCESS_TOKEN"]
BASE_URL = "https://graph.microsoft.com/v1.0"
HEADERS = {
    "Authorization": f"Bearer {GRAPH_ACCESS_TOKEN}",
    "Content-Type": "application/json",
}
TIMEZONE = os.environ.get("GRAPH_TIMEZONE", "Eastern Standard Time")
SLOT_DURATION_MINS = int(os.environ.get("MEETING_SLOT_DURATION_MINS", 60))
BOOKING_WINDOW_DAYS = int(os.environ.get("MEETING_BOOKING_WINDOW_DAYS", 14))
BUSINESS_HOURS_START = int(os.environ.get("MEETING_HOURS_START", 9))
BUSINESS_HOURS_END = int(os.environ.get("MEETING_HOURS_END", 17))


def get_free_slots() -> list[str]:
    """Returns ISO-8601 datetime strings for open meeting slots by checking the organizer's calendar."""
    tz = datetime.timezone.utc
    now = datetime.datetime.now(tz)
    window_end = now + datetime.timedelta(days=BOOKING_WINDOW_DAYS)

    resp = requests.get(
        f"{BASE_URL}/me/calendarView",
        headers=HEADERS,
        params={
            "startDateTime": now.isoformat(),
            "endDateTime": window_end.isoformat(),
            "$select": "start,end,showAs,isCancelled",
            "$top": 200,
        },
        timeout=15,
    )
    resp.raise_for_status()

    # Build busy ranges from non-free, non-cancelled events
    busy_ranges: list[tuple[datetime.datetime, datetime.datetime]] = []
    for event in resp.json().get("value", []):
        if event.get("isCancelled") or event.get("showAs") == "free":
            continue
        try:
            start = datetime.datetime.fromisoformat(
                event["start"]["dateTime"]
            ).replace(tzinfo=tz)
            end = datetime.datetime.fromisoformat(
                event["end"]["dateTime"]
            ).replace(tzinfo=tz)
            busy_ranges.append((start, end))
        except (KeyError, ValueError):
            pass

    def is_free(slot_start: datetime.datetime) -> bool:
        slot_end = slot_start + datetime.timedelta(minutes=SLOT_DURATION_MINS)
        return not any(
            slot_start < b_end and slot_end > b_start
            for b_start, b_end in busy_ranges
        )

    # Walk through the booking window day by day (weekdays only)
    duration = datetime.timedelta(minutes=SLOT_DURATION_MINS)
    free_slots: list[str] = []
    current_day = now.date() + datetime.timedelta(days=1)

    while current_day <= window_end.date():
        if current_day.weekday() < 5:  # Mon–Fri
            slot = datetime.datetime.combine(
                current_day, datetime.time(BUSINESS_HOURS_START, 0), tzinfo=tz
            )
            day_end = datetime.datetime.combine(
                current_day, datetime.time(BUSINESS_HOURS_END, 0), tzinfo=tz
            )
            while slot + duration <= day_end:
                if is_free(slot):
                    free_slots.append(slot.replace(microsecond=0).isoformat())
                slot += duration
        current_day += datetime.timedelta(days=1)

    logging.info(
        "Found %d free slot(s) over the next %d day(s)", len(free_slots), BOOKING_WINDOW_DAYS
    )
    return free_slots


def create_event(
    subject: str,
    iso_slot: str,
    attendee_emails: list[str],
) -> dict:
    """Creates an Outlook calendar event for the chosen slot."""
    start = datetime.datetime.fromisoformat(iso_slot)
    end = start + datetime.timedelta(minutes=SLOT_DURATION_MINS)
    payload = {
        "subject": subject,
        "start": {"dateTime": start.isoformat(), "timeZone": TIMEZONE},
        "end": {"dateTime": end.isoformat(), "timeZone": TIMEZONE},
        "attendees": [
            {"emailAddress": {"address": email}, "type": "required"}
            for email in attendee_emails
        ],
    }
    resp = requests.post(
        f"{BASE_URL}/me/events",
        headers=HEADERS,
        json=payload,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


class MeetingSchedulerController(guava.CallController):
    def __init__(self):
        super().__init__()

        # Fetch the organizer's free slots before the call so DatetimeFilter
        # is ready to answer natural-language time queries immediately.
        free_slots = get_free_slots()
        self.datetime_filter = DatetimeFilter(source_list=free_slots)

        self.set_persona(
            organization_name="Meridian Partners",
            agent_name="Jamie",
            agent_purpose=(
                "to help Meridian Partners employees schedule meetings by finding "
                "available times and booking directly into Outlook"
            ),
        )

        self.set_task(
            objective=(
                "A team member has called to schedule a meeting. Collect the title, "
                "attendees, and a time that works, then book it."
            ),
            checklist=[
                guava.Say(
                    "Thank you for calling Meridian Partners scheduling. I'm Jamie. "
                    "I can find an available time and book the meeting for you right now."
                ),
                guava.Field(
                    key="meeting_title",
                    field_type="text",
                    description="Ask for the meeting title or topic.",
                    required=True,
                ),
                guava.Field(
                    key="attendee_emails",
                    field_type="text",
                    description=(
                        "Ask for the email addresses of the people to invite, "
                        "separated by spaces or commas."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="appointment_time",
                    field_type="calendar_slot",
                    description=(
                        "Find a meeting time that works for the caller. "
                        "Ask for their preference and present available options."
                    ),
                    choice_generator=self.filter_slots,
                ),
            ],
            on_complete=self.book_meeting,
        )

        self.accept_call()

    def filter_slots(self, query: str) -> list[str]:
        return self.datetime_filter.filter(query, max_results=3)

    def book_meeting(self):
        title = self.get_field("meeting_title") or "Meeting"
        attendees_raw = self.get_field("attendee_emails") or ""
        slot = self.get_field("appointment_time")

        attendees = [e.strip() for e in attendees_raw.replace(",", " ").split() if "@" in e]

        if not slot:
            self.hangup(
                final_instructions=(
                    "Apologize — no meeting time was confirmed. "
                    "Ask the caller to try again or book directly in Outlook. Thank them."
                )
            )
            return

        logging.info("Booking '%s' at %s for %s", title, slot, attendees)

        try:
            start_dt = datetime.datetime.fromisoformat(slot)
            end_dt = start_dt + datetime.timedelta(minutes=SLOT_DURATION_MINS)
            time_label = (
                f"{start_dt.strftime('%A, %B %-d')} from "
                f"{start_dt.strftime('%-I:%M %p')} to {end_dt.strftime('%-I:%M %p')}"
            )
            create_event(title, slot, attendees)
            logging.info("Event created: %s at %s", title, slot)
            self.hangup(
                final_instructions=(
                    f"Let the caller know the meeting '{title}' has been booked for {time_label}. "
                    "Invites have been sent to all attendees. "
                    "Thank them for using Meridian Partners scheduling."
                )
            )
        except Exception as e:
            logging.error("Event creation failed: %s", e)
            self.hangup(
                final_instructions=(
                    "Apologize — there was a technical issue creating the calendar event. "
                    "Ask the caller to try again or book directly in Outlook. Thank them."
                )
            )


if __name__ == "__main__":
    logging_utils.configure_logging()
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=MeetingSchedulerController,
    )
