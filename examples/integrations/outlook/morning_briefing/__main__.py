import guava
import os
import logging
import argparse
import requests
from datetime import datetime, date

logging.basicConfig(level=logging.INFO)

GRAPH_ACCESS_TOKEN = os.environ["GRAPH_ACCESS_TOKEN"]
BASE_URL = "https://graph.microsoft.com/v1.0"
HEADERS = {
    "Authorization": f"Bearer {GRAPH_ACCESS_TOKEN}",
    "Content-Type": "application/json",
}


def get_todays_events(user_id: str) -> list[dict]:
    """Returns all non-cancelled events for the given user today, ordered by start time."""
    today = date.today().isoformat()
    resp = requests.get(
        f"{BASE_URL}/users/{user_id}/calendarView",
        headers=HEADERS,
        params={
            "startDateTime": f"{today}T00:00:00Z",
            "endDateTime": f"{today}T23:59:59Z",
            "$select": "subject,start,end,location,organizer,isOnlineMeeting,isAllDay,isCancelled",
            "$orderby": "start/dateTime",
            "$top": 15,
        },
        timeout=15,
    )
    resp.raise_for_status()
    return [e for e in resp.json().get("value", []) if not e.get("isCancelled")]


def get_unread_important_count(user_id: str) -> int:
    """Returns the count of unread high-importance messages in the inbox."""
    resp = requests.get(
        f"{BASE_URL}/users/{user_id}/mailFolders/inbox/messages",
        headers=HEADERS,
        params={
            "$filter": "isRead eq false and importance eq 'high'",
            "$select": "id",
            "$top": 25,
            "$count": "true",
        },
        headers={**HEADERS, "ConsistencyLevel": "eventual"},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("@odata.count", len(data.get("value", [])))


def format_event_spoken(event: dict) -> str:
    """Returns a natural-language description of an event for the agent to read aloud."""
    subject = event.get("subject") or "an untitled event"
    if event.get("isAllDay"):
        return f"{subject}, all day"
    start_str = event.get("start", {}).get("dateTime", "")
    end_str = event.get("end", {}).get("dateTime", "")
    location = event.get("location", {}).get("displayName", "")
    online = event.get("isOnlineMeeting", False)
    try:
        start_dt = datetime.fromisoformat(start_str)
        end_dt = datetime.fromisoformat(end_str)
        time_str = (
            f"{start_dt.strftime('%-I:%M %p')} to {end_dt.strftime('%-I:%M %p')}"
        )
    except (ValueError, AttributeError):
        time_str = start_str

    result = f"{subject} from {time_str}"
    if online:
        result += " (online)"
    elif location:
        result += f" in {location}"
    return result


class MorningBriefingController(guava.CallController):
    def __init__(self, person_name: str, user_id: str):
        super().__init__()
        self.person_name = person_name
        self.user_id = user_id
        self.events: list[dict] = []
        self.unread_important = 0

        # Fetch today's calendar and inbox counts before the call
        try:
            self.events = get_todays_events(user_id)
            logging.info(
                "Today's events for %s: %d meeting(s)", user_id, len(self.events)
            )
        except Exception as e:
            logging.error("Failed to fetch events for %s: %s", user_id, e)

        try:
            self.unread_important = get_unread_important_count(user_id)
            logging.info(
                "Unread high-importance messages for %s: %d", user_id, self.unread_important
            )
        except Exception as e:
            logging.warning("Failed to fetch unread count for %s: %s", user_id, e)

        self.set_persona(
            organization_name="Meridian Partners",
            agent_name="Riley",
            agent_purpose=(
                "to give Meridian Partners employees a quick voice briefing on their day — "
                "meetings, important emails, and anything they need to know before the day begins"
            ),
        )

        self.reach_person(
            contact_full_name=person_name,
            on_success=self.deliver_briefing,
            on_failure=self.recipient_unavailable,
        )

    def deliver_briefing(self):
        today_label = date.today().strftime("%A, %B %-d")
        event_count = len(self.events)

        if event_count == 0 and self.unread_important == 0:
            self.hangup(
                final_instructions=(
                    f"Greet {self.person_name} and let them know today, {today_label}, "
                    "is clear — no meetings scheduled and no urgent emails. "
                    "Wish them a productive day."
                )
            )
            return

        # Build the meeting briefing
        meeting_lines = ""
        if event_count > 0:
            formatted = "; ".join(format_event_spoken(e) for e in self.events)
            meeting_lines = (
                f"You have {event_count} meeting{'s' if event_count != 1 else ''} today: "
                f"{formatted}."
            )

        # Build the email note
        email_note = ""
        if self.unread_important > 0:
            email_note = (
                f"You also have {self.unread_important} unread high-priority "
                f"email{'s' if self.unread_important != 1 else ''} in your inbox."
            )

        self.set_task(
            objective=(
                f"Brief {self.person_name} on their day: meetings and any important emails. "
                "Ask if they have questions about any item."
            ),
            checklist=[
                guava.Say(
                    f"Good morning, {self.person_name}! This is Riley from Meridian Partners "
                    f"with your daily briefing for {today_label}. "
                    + (f"{meeting_lines} " if meeting_lines else "No meetings today. ")
                    + (email_note if email_note else "")
                ),
                guava.Field(
                    key="questions",
                    field_type="text",
                    description=(
                        "Ask if they have any questions about today's schedule "
                        "or anything specific they'd like to follow up on. "
                        "Capture their response or 'none' if they're all set."
                    ),
                    required=True,
                ),
            ],
            on_complete=self.wrap_up,
        )

    def wrap_up(self):
        questions = self.get_field("questions") or ""
        has_questions = questions.strip().lower() not in ("none", "no", "nope", "all good", "")

        logging.info(
            "Morning briefing wrap-up for %s — questions: %s", self.person_name, questions
        )

        if has_questions:
            self.hangup(
                final_instructions=(
                    f"Address {self.person_name}'s question or request: '{questions}'. "
                    "Answer using only the calendar context you've already shared. "
                    "If it requires further research, let them know their EA or team can follow up. "
                    "Wish them a productive day."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Wish {self.person_name} a great and productive {date.today().strftime('%A')}. "
                    "Keep it warm and brief."
                )
            )

    def recipient_unavailable(self):
        logging.info("Unable to reach %s for morning briefing", self.person_name)
        event_count = len(self.events)
        meeting_note = (
            f"a quick note: you have {event_count} meeting{'s' if event_count != 1 else ''} today"
            if event_count > 0
            else "your calendar looks clear today"
        )
        self.hangup(
            final_instructions=(
                f"Leave a brief, upbeat voicemail for {self.person_name} from Meridian Partners. "
                f"Let them know you called with their morning briefing — {meeting_note}. "
                "Tell them to check their Outlook calendar for details. Keep it very brief."
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Outbound morning briefing call with today's Outlook calendar summary."
    )
    parser.add_argument("phone", help="Recipient phone number (E.164, e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Recipient's full name")
    parser.add_argument(
        "--user-id",
        required=True,
        help="Microsoft 365 user ID or UPN (email) for calendar/inbox lookup",
    )
    args = parser.parse_args()

    logging.info(
        "Initiating morning briefing call to %s (%s)", args.name, args.phone
    )

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=MorningBriefingController(
            person_name=args.name,
            user_id=args.user_id,
        ),
    )
