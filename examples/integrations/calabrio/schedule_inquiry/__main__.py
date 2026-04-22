import guava
import os
import logging
import json
import requests
from datetime import datetime, timezone, timedelta

logging.basicConfig(level=logging.INFO)

CALABRIO_BASE_URL = os.environ["CALABRIO_BASE_URL"]  # e.g. https://mycompany.calabriocloud.com
CALABRIO_API_KEY = os.environ["CALABRIO_API_KEY"]

HEADERS = {
    "apiKey": CALABRIO_API_KEY,
    "Content-Type": "application/json",
    "Accept": "application/json",
}


def find_agent_by_email(email: str) -> dict | None:
    """Looks up a Calabrio agent by email address."""
    resp = requests.get(
        f"{CALABRIO_BASE_URL}/api/agents",
        headers=HEADERS,
        params={"email": email},
        timeout=10,
    )
    resp.raise_for_status()
    agents = resp.json()
    if isinstance(agents, list) and agents:
        return agents[0]
    return None


def get_agent_schedule(agent_id: str, date: str) -> list:
    """Returns the agent's scheduled shifts for the given date (YYYY-MM-DD)."""
    resp = requests.get(
        f"{CALABRIO_BASE_URL}/api/agents/{agent_id}/schedule",
        headers=HEADERS,
        params={"startDate": date, "endDate": date},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else data.get("scheduledActivities", [])


def format_shift(shift: dict) -> str:
    activity = shift.get("activityName", shift.get("activity", "shift"))
    start = shift.get("startTime", shift.get("start", ""))
    end = shift.get("endTime", shift.get("end", ""))
    # Trim seconds if present (HH:MM:SS → HH:MM)
    start_display = start[:5] if len(start) >= 5 else start
    end_display = end[:5] if len(end) >= 5 else end
    return f"{activity} from {start_display} to {end_display}"


class ScheduleInquiryController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Horizon Contact Center",
            agent_name="Riley",
            agent_purpose=(
                "to help contact center agents check their upcoming work schedules"
            ),
        )

        self.set_task(
            objective=(
                "An agent is calling to check their schedule. Collect their email and "
                "the date they want to check, then look it up in Calabrio."
            ),
            checklist=[
                guava.Say(
                    "Thank you for calling Horizon Contact Center workforce management. "
                    "I'm Riley, and I can look up your schedule."
                ),
                guava.Field(
                    key="agent_email",
                    field_type="text",
                    description="Ask for the agent's work email address.",
                    required=True,
                ),
                guava.Field(
                    key="date_preference",
                    field_type="multiple_choice",
                    description="Ask which date they'd like to check.",
                    choices=["today", "tomorrow", "specific date"],
                    required=True,
                ),
                guava.Field(
                    key="specific_date",
                    field_type="text",
                    description=(
                        "If they chose 'specific date', ask for the date in YYYY-MM-DD format. "
                        "Skip if they selected today or tomorrow."
                    ),
                    required=False,
                ),
            ],
            on_complete=self.look_up_schedule,
        )

        self.accept_call()

    def look_up_schedule(self):
        email = (self.get_field("agent_email") or "").strip().lower()
        date_pref = self.get_field("date_preference")
        specific = (self.get_field("specific_date") or "").strip()

        today = datetime.now(timezone.utc).date()
        if date_pref == "today":
            target_date = today
        elif date_pref == "tomorrow":
            target_date = today + timedelta(days=1)
        elif specific:
            try:
                target_date = datetime.strptime(specific, "%Y-%m-%d").date()
            except ValueError:
                target_date = today
        else:
            target_date = today

        date_str = target_date.strftime("%Y-%m-%d")
        date_label = (
            "today" if target_date == today
            else "tomorrow" if target_date == today + timedelta(days=1)
            else target_date.strftime("%A, %B %-d")
        )

        logging.info("Calabrio schedule lookup for %s on %s", email, date_str)

        try:
            agent = find_agent_by_email(email)
        except Exception as e:
            logging.error("Agent lookup failed: %s", e)
            agent = None

        if not agent:
            self.hangup(
                final_instructions=(
                    "Let the caller know we couldn't find an agent account for that email address. "
                    "Ask them to verify their work email and try again, or contact their "
                    "workforce management team. Thank them for calling."
                )
            )
            return

        agent_id = agent.get("id") or agent.get("agentId", "")
        agent_name = agent.get("name") or agent.get("displayName", "there")
        first_name = agent_name.split()[0] if agent_name else "there"

        try:
            shifts = get_agent_schedule(agent_id, date_str)
        except Exception as e:
            logging.error("Schedule lookup failed for agent %s: %s", agent_id, e)
            shifts = []

        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": "Riley",
            "use_case": "schedule_inquiry",
            "caller_email": email,
            "agent_id": agent_id,
            "date": date_str,
            "shifts_found": len(shifts),
            "shifts": shifts,
        }
        print(json.dumps(result, indent=2))

        if not shifts:
            self.hangup(
                final_instructions=(
                    f"Let {first_name} know that no scheduled shifts were found for {date_label}. "
                    "It's possible they have a day off or their schedule hasn't been published yet. "
                    "Suggest they check Calabrio directly or contact their supervisor. "
                    "Thank them for calling."
                )
            )
            return

        shift_descriptions = [format_shift(s) for s in shifts]
        shift_text = "; then ".join(shift_descriptions)

        self.hangup(
            final_instructions=(
                f"Let {first_name} know their schedule for {date_label}: {shift_text}. "
                "If they have more than one activity, read them in order. "
                "Thank them for calling Horizon Contact Center workforce management."
            )
        )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=ScheduleInquiryController,
    )
