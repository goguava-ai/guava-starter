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
TIMEZONE = os.environ.get("GRAPH_TIMEZONE", "Eastern Standard Time")


def search_events(subject_fragment: str, days_ahead: int = 30) -> list[dict]:
    """Returns upcoming events whose subject contains the given fragment."""
    today = date.today().isoformat()
    future = (date.today() + timedelta(days=days_ahead)).isoformat()
    resp = requests.get(
        f"{BASE_URL}/me/calendarView",
        headers=HEADERS,
        params={
            "startDateTime": f"{today}T00:00:00Z",
            "endDateTime": f"{future}T23:59:59Z",
            "$select": "id,subject,start,end,organizer",
            "$filter": f"contains(subject,'{subject_fragment}')",
            "$orderby": "start/dateTime",
            "$top": 5,
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("value", [])


def reschedule_event(
    event_id: str,
    new_date: str,
    new_start_time: str,
    new_end_time: str,
) -> dict:
    """Updates an event's start and end times via PATCH."""
    payload = {
        "start": {"dateTime": f"{new_date}T{new_start_time}:00", "timeZone": TIMEZONE},
        "end": {"dateTime": f"{new_date}T{new_end_time}:00", "timeZone": TIMEZONE},
    }
    resp = requests.patch(
        f"{BASE_URL}/me/events/{event_id}",
        headers=HEADERS,
        json=payload,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def format_event_summary(event: dict) -> str:
    subject = event.get("subject") or "Untitled"
    start_str = event.get("start", {}).get("dateTime", "")
    try:
        dt = datetime.fromisoformat(start_str)
        return f"'{subject}' on {dt.strftime('%A, %B %-d at %-I:%M %p')}"
    except (ValueError, AttributeError):
        return f"'{subject}'"


class MeetingRescheduleController(guava.CallController):
    def __init__(self):
        super().__init__()
        self._event: dict = {}

        self.set_persona(
            organization_name="Meridian Partners",
            agent_name="Morgan",
            agent_purpose=(
                "to help Meridian Partners employees reschedule existing Outlook meetings "
                "over the phone"
            ),
        )

        self.set_task(
            objective=(
                "A team member has called to move an existing meeting to a new time. "
                "Find the meeting and update it with the new date and time."
            ),
            checklist=[
                guava.Say(
                    "Thank you for calling Meridian Partners. I'm Morgan. "
                    "I can reschedule a meeting for you — I'll need to find it first."
                ),
                guava.Field(
                    key="meeting_name",
                    field_type="text",
                    description=(
                        "Ask for the meeting name or a keyword from the subject "
                        "so we can locate it on their calendar."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="new_date",
                    field_type="date",
                    description="Ask for the new date they'd like to move the meeting to.",
                    required=True,
                ),
                guava.Field(
                    key="new_start_time",
                    field_type="text",
                    description=(
                        "Ask for the new start time. Capture in 24-hour HH:MM format "
                        "(e.g., 14:30 for 2:30 PM)."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="new_end_time",
                    field_type="text",
                    description=(
                        "Ask for the new end time. Capture in 24-hour HH:MM format."
                    ),
                    required=True,
                ),
            ],
            on_complete=self.find_and_reschedule,
        )

        self.accept_call()

    def find_and_reschedule(self):
        meeting_name = self.get_field("meeting_name") or ""
        new_date = self.get_field("new_date") or ""
        new_start = self.get_field("new_start_time") or ""
        new_end = self.get_field("new_end_time") or ""

        logging.info(
            "Rescheduling '%s' to %s %s–%s", meeting_name, new_date, new_start, new_end
        )

        try:
            events = search_events(meeting_name)
        except Exception as e:
            logging.error("Event search failed: %s", e)
            events = []

        if not events:
            self.hangup(
                final_instructions=(
                    f"Let the caller know we couldn't find a meeting matching '{meeting_name}' "
                    "in their upcoming calendar. Ask them to double-check the name or reschedule "
                    "directly in Outlook. Thank them for calling."
                )
            )
            return

        self._event = events[0]
        event_id = self._event["id"]
        old_summary = format_event_summary(self._event)

        try:
            dt = datetime.strptime(new_date, "%Y-%m-%d")
            new_date_label = dt.strftime("%A, %B %-d")
        except ValueError:
            new_date_label = new_date

        try:
            start_dt = datetime.strptime(new_start, "%H:%M")
            end_dt = datetime.strptime(new_end, "%H:%M")
            time_label = (
                f"{start_dt.strftime('%-I:%M %p')} to {end_dt.strftime('%-I:%M %p')}"
            )
        except ValueError:
            time_label = f"{new_start} to {new_end}"

        logging.info(
            "Updating event %s to %s %s", event_id, new_date_label, time_label
        )

        try:
            reschedule_event(event_id, new_date, new_start, new_end)
        except Exception as e:
            logging.error("Reschedule failed for event %s: %s", event_id, e)
            self.hangup(
                final_instructions=(
                    f"Apologize — there was an issue rescheduling {old_summary}. "
                    "Ask the caller to update the meeting directly in Outlook. Thank them."
                )
            )
            return

        self.hangup(
            final_instructions=(
                f"Let the caller know {old_summary} has been rescheduled to "
                f"{new_date_label} from {time_label}. "
                "All attendees will receive an updated invite. "
                "Thank them for calling Meridian Partners."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=MeetingRescheduleController,
    )
