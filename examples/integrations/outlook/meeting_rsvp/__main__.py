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
            "$select": "id,subject,start,end,responseStatus,organizer,attendees",
            "$filter": f"contains(subject,'{subject_fragment}')",
            "$orderby": "start/dateTime",
            "$top": 5,
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("value", [])


def rsvp_event(event_id: str, response: str, comment: str = "") -> None:
    """Accepts, tentatively accepts, or declines a meeting invite."""
    action_map = {
        "accept": "accept",
        "tentative": "tentativelyAccept",
        "decline": "decline",
    }
    action = action_map.get(response, "accept")
    payload = {"comment": comment, "sendResponse": True}
    resp = requests.post(
        f"{BASE_URL}/me/events/{event_id}/{action}",
        headers=HEADERS,
        json=payload,
        timeout=15,
    )
    resp.raise_for_status()


def format_event_summary(event: dict) -> str:
    """Returns a spoken summary of an event for the agent to read."""
    subject = event.get("subject") or "Untitled"
    start_str = event.get("start", {}).get("dateTime", "")
    organizer = event.get("organizer", {}).get("emailAddress", {}).get("name", "")
    try:
        dt = datetime.fromisoformat(start_str)
        time_str = dt.strftime("%A, %B %-d at %-I:%M %p")
    except (ValueError, AttributeError):
        time_str = start_str
    result = f"'{subject}' on {time_str}"
    if organizer:
        result += f", organized by {organizer}"
    return result


class MeetingRSVPController(guava.CallController):
    def __init__(self):
        super().__init__()
        self._event: dict = {}

        self.set_persona(
            organization_name="Meridian Partners",
            agent_name="Riley",
            agent_purpose=(
                "to help Meridian Partners employees accept, tentatively accept, "
                "or decline meeting invitations over the phone"
            ),
        )

        self.set_task(
            objective=(
                "A team member has called to respond to a meeting invitation. "
                "Find the meeting and record their RSVP."
            ),
            checklist=[
                guava.Say(
                    "Thank you for calling Meridian Partners. I'm Riley. "
                    "I can RSVP to a meeting invite for you — I just need to find it."
                ),
                guava.Field(
                    key="meeting_name",
                    field_type="text",
                    description=(
                        "Ask for the meeting name or a keyword from the subject line "
                        "so we can locate the invite."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="rsvp_response",
                    field_type="multiple_choice",
                    description="Ask how they'd like to respond to the invite.",
                    choices=["accept", "tentative", "decline"],
                    required=True,
                ),
                guava.Field(
                    key="rsvp_comment",
                    field_type="text",
                    description=(
                        "Ask if they'd like to include a brief note with their response "
                        "(for example, 'Running 5 minutes late' or 'Will join by video'). "
                        "This is optional."
                    ),
                    required=False,
                ),
            ],
            on_complete=self.find_and_rsvp,
        )

        self.accept_call()

    def find_and_rsvp(self):
        meeting_name = self.get_field("meeting_name") or ""
        response = self.get_field("rsvp_response") or "accept"
        comment = self.get_field("rsvp_comment") or ""

        logging.info("Searching for meeting '%s' to RSVP as '%s'", meeting_name, response)

        try:
            events = search_events(meeting_name)
        except Exception as e:
            logging.error("Event search failed: %s", e)
            events = []

        if not events:
            self.hangup(
                final_instructions=(
                    f"Let the caller know we couldn't find a meeting with '{meeting_name}' "
                    "in their upcoming calendar. Ask them to double-check the meeting name "
                    "or respond directly in Outlook. Thank them for calling."
                )
            )
            return

        self._event = events[0]
        event_id = self._event["id"]
        event_summary = format_event_summary(self._event)

        logging.info(
            "RSVPing event '%s' (id: %s) as: %s",
            self._event.get("subject"), event_id, response,
        )

        try:
            rsvp_event(event_id, response, comment)
        except Exception as e:
            logging.error("RSVP failed for event %s: %s", event_id, e)
            self.hangup(
                final_instructions=(
                    f"Apologize — there was an issue submitting the RSVP for {event_summary}. "
                    "Ask the caller to respond directly in Outlook. Thank them for calling."
                )
            )
            return

        response_labels = {
            "accept": "accepted",
            "tentative": "tentatively accepted",
            "decline": "declined",
        }
        response_label = response_labels.get(response, response)
        logging.info("RSVP submitted: %s for event %s", response_label, event_id)

        self.hangup(
            final_instructions=(
                f"Let the caller know they've {response_label} {event_summary}. "
                + (f"The note '{comment}' was included with the response. " if comment else "")
                + "The organizer has been notified. "
                "Thank them for calling Meridian Partners."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=MeetingRSVPController,
    )
