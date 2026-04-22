import guava
import os
import logging
from guava import logging_utils
import requests
from datetime import datetime, date, timedelta


GRAPH_ACCESS_TOKEN = os.environ["GRAPH_ACCESS_TOKEN"]
BASE_URL = "https://graph.microsoft.com/v1.0"
HEADERS = {
    "Authorization": f"Bearer {GRAPH_ACCESS_TOKEN}",
    "Content-Type": "application/json",
}


def get_events_for_date(user_id: str, target_date: str) -> list[dict]:
    """Returns events for a user on the given date (YYYY-MM-DD). Uses 'me' if user_id is empty."""
    path = f"users/{user_id}" if user_id else "me"
    resp = requests.get(
        f"{BASE_URL}/{path}/calendarView",
        headers=HEADERS,
        params={
            "startDateTime": f"{target_date}T00:00:00Z",
            "endDateTime": f"{target_date}T23:59:59Z",
            "$select": "subject,start,end,location,organizer,isAllDay,isCancelled",
            "$orderby": "start/dateTime",
            "$top": 20,
        },
        timeout=15,
    )
    resp.raise_for_status()
    return [e for e in resp.json().get("value", []) if not e.get("isCancelled")]


def format_event_brief(event: dict) -> str:
    """Returns a short spoken summary of a calendar event."""
    subject = event.get("subject") or "Untitled event"
    if event.get("isAllDay"):
        return f"{subject} (all day)"
    start_str = event.get("start", {}).get("dateTime", "")
    end_str = event.get("end", {}).get("dateTime", "")
    location = event.get("location", {}).get("displayName", "")
    try:
        start_dt = datetime.fromisoformat(start_str)
        end_dt = datetime.fromisoformat(end_str)
        time_range = f"{start_dt.strftime('%-I:%M %p')} to {end_dt.strftime('%-I:%M %p')}"
    except (ValueError, AttributeError):
        time_range = start_str
    result = f"{subject} from {time_range}"
    if location:
        result += f" in {location}"
    return result


def resolve_date(date_choice: str) -> str:
    """Maps a relative date choice to YYYY-MM-DD."""
    today = date.today()
    mapping = {
        "today": today,
        "tomorrow": today + timedelta(days=1),
        "this monday": today + timedelta(days=(0 - today.weekday()) % 7),
        "next monday": today + timedelta(days=(7 - today.weekday()) % 7 + 7),
    }
    return mapping.get(date_choice.lower(), today).isoformat()


class CalendarCheckController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Meridian Partners",
            agent_name="Alex",
            agent_purpose=(
                "to help Meridian Partners employees quickly check their Outlook calendar "
                "over the phone"
            ),
        )

        self.set_task(
            objective=(
                "A team member has called to check their calendar. Ask which day they want to "
                "review and optionally whose calendar, then read back their schedule."
            ),
            checklist=[
                guava.Say(
                    "Thank you for calling Meridian Partners. I'm Alex. "
                    "I can read your Outlook calendar for any day — what would you like to check?"
                ),
                guava.Field(
                    key="date_choice",
                    field_type="multiple_choice",
                    description=(
                        "Ask which day they want to check. "
                        "If they say a specific date, capture it; otherwise map it to one of these."
                    ),
                    choices=["today", "tomorrow", "this monday", "next monday", "specific date"],
                    required=True,
                ),
                guava.Field(
                    key="specific_date",
                    field_type="date",
                    description=(
                        "If they chose 'specific date', ask for the date. "
                        "Skip this if they chose today or tomorrow."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="user_id",
                    field_type="text",
                    description=(
                        "Ask if they want to check their own calendar or a colleague's. "
                        "If a colleague's, ask for their email address. "
                        "Leave blank for their own calendar."
                    ),
                    required=False,
                ),
            ],
            on_complete=self.read_calendar,
        )

        self.accept_call()

    def read_calendar(self):
        date_choice = self.get_field("date_choice") or "today"
        specific_date = self.get_field("specific_date") or ""
        user_id = (self.get_field("user_id") or "").strip()

        if date_choice == "specific date" and specific_date:
            target_date = specific_date.strip()
        else:
            target_date = resolve_date(date_choice)

        try:
            dt = datetime.strptime(target_date, "%Y-%m-%d")
            date_label = dt.strftime("%A, %B %-d")
        except ValueError:
            date_label = target_date

        whose = f"the calendar for {user_id}" if user_id else "your calendar"
        logging.info("Fetching events for user='%s' date='%s'", user_id or "me", target_date)

        try:
            events = get_events_for_date(user_id, target_date)
        except Exception as e:
            logging.error("Calendar fetch failed: %s", e)
            self.hangup(
                final_instructions=(
                    f"Apologize — there was a technical issue fetching {whose} for {date_label}. "
                    "Ask the caller to check Outlook directly. Thank them for calling."
                )
            )
            return

        if not events:
            self.hangup(
                final_instructions=(
                    f"Let the caller know {whose} is clear for {date_label} — no events scheduled. "
                    "Thank them for calling Meridian Partners."
                )
            )
            return

        count = len(events)
        summaries = "; ".join(format_event_brief(e) for e in events)
        logging.info("Found %d event(s) for %s on %s", count, user_id or "me", target_date)

        self.hangup(
            final_instructions=(
                f"Read back {whose} for {date_label}. "
                f"There {'is' if count == 1 else 'are'} {count} "
                f"event{'s' if count != 1 else ''}: {summaries}. "
                "Read each one clearly, pausing between events. "
                "Thank them for calling Meridian Partners."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=CalendarCheckController,
    )
