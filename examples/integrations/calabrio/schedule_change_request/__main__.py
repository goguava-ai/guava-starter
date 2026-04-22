import json
import logging
import os
from datetime import datetime, timezone

import guava
import requests
from guava import logging_utils

CALABRIO_BASE_URL = os.environ["CALABRIO_BASE_URL"]
CALABRIO_API_KEY = os.environ["CALABRIO_API_KEY"]

HEADERS = {
    "apiKey": CALABRIO_API_KEY,
    "Content-Type": "application/json",
    "Accept": "application/json",
}


def find_agent_by_email(email: str) -> dict | None:
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
    resp = requests.get(
        f"{CALABRIO_BASE_URL}/api/agents/{agent_id}/schedule",
        headers=HEADERS,
        params={"startDate": date, "endDate": date},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else data.get("scheduledActivities", [])


def submit_schedule_change_request(
    agent_id: str,
    request_type: str,
    date: str,
    reason: str,
    details: str,
) -> dict:
    """Submits a schedule change or time-off request in Calabrio."""
    payload = {
        "agentId": agent_id,
        "requestType": request_type,  # e.g. "TimeOff", "ShiftSwap", "StartTimeChange"
        "requestDate": date,
        "reason": reason,
        "notes": details,
        "status": "pending",
        "submittedAt": datetime.now(timezone.utc).isoformat(),
    }
    resp = requests.post(
        f"{CALABRIO_BASE_URL}/api/scheduling/requests",
        headers=HEADERS,
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


agent = guava.Agent(
    name="Taylor",
    organization="Horizon Contact Center",
    purpose=(
        "to help contact center agents submit schedule change requests and time-off "
        "requests through Calabrio"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "submit_request",
        objective=(
            "An agent is calling to request a schedule change or time off. "
            "Collect their identity, the type of request, date, and reason."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Horizon Contact Center workforce management. "
                "I'm Taylor, and I can help you submit a schedule change request."
            ),
            guava.Field(
                key="agent_email",
                field_type="text",
                description="Ask for the agent's work email address to look up their profile.",
                required=True,
            ),
            guava.Field(
                key="request_type",
                field_type="multiple_choice",
                description="Ask what type of schedule change they're requesting.",
                choices=["time off", "shift swap", "start time change", "early release"],
                required=True,
            ),
            guava.Field(
                key="request_date",
                field_type="text",
                description="Ask for the date they need the change for in YYYY-MM-DD format.",
                required=True,
            ),
            guava.Field(
                key="reason",
                field_type="text",
                description=(
                    "Ask them to briefly explain the reason for the request. "
                    "This will be visible to their supervisor."
                ),
                required=True,
            ),
            guava.Field(
                key="additional_details",
                field_type="text",
                description=(
                    "Ask if there are any additional details — for example, a preferred "
                    "swap partner for a shift swap, or a preferred start time for a "
                    "start time change. Optional."
                ),
                required=False,
            ),
        ],
    )


@agent.on_task_complete("submit_request")
def on_done(call: guava.Call) -> None:
    email = (call.get_field("agent_email") or "").strip().lower()
    request_type = call.get_field("request_type")
    request_date = (call.get_field("request_date") or "").strip()
    reason = call.get_field("reason")
    details = call.get_field("additional_details") or ""

    type_map = {
        "time off": "TimeOff",
        "shift swap": "ShiftSwap",
        "start time change": "StartTimeChange",
        "early release": "EarlyRelease",
    }
    calabrio_type = type_map.get(request_type, request_type)

    logging.info(
        "Schedule change request from %s — type: %s, date: %s",
        email, request_type, request_date,
    )

    try:
        agent_record = find_agent_by_email(email)
    except Exception as e:
        logging.error("Agent lookup failed: %s", e)
        agent_record = None

    if not agent_record:
        call.hangup(
            final_instructions=(
                "Let the caller know we couldn't find their agent profile. "
                "Ask them to verify their email and try again, or submit the request "
                "directly through the Calabrio portal. Thank them for calling."
            )
        )
        return

    agent_id = agent_record.get("id") or agent_record.get("agentId", "")
    agent_name = agent_record.get("name") or agent_record.get("displayName", "there")
    first_name = agent_name.split()[0] if agent_name else "there"

    # Format date for display
    try:
        date_obj = datetime.strptime(request_date, "%Y-%m-%d").date()
        date_display = date_obj.strftime("%A, %B %-d")
    except ValueError:
        date_display = request_date

    try:
        result = submit_schedule_change_request(
            agent_id=agent_id,
            request_type=calabrio_type,
            date=request_date,
            reason=reason,
            details=details,
        )
        request_id = result.get("id") or result.get("requestId", "")
        logging.info("Schedule change request submitted: %s", request_id)

        outcome = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": "Taylor",
            "use_case": "schedule_change_request",
            "caller_email": email,
            "agent_id": agent_id,
            "request_type": request_type,
            "request_date": request_date,
            "reason": reason,
            "request_id": str(request_id),
        }
        print(json.dumps(outcome, indent=2))

        call.hangup(
            final_instructions=(
                f"Let {first_name} know their {request_type} request for {date_display} "
                f"has been submitted successfully. The request ID is {request_id}. "
                "Their supervisor will review and respond within one business day. "
                "They can also check the status in the Calabrio portal. "
                "Thank them for calling Horizon Contact Center workforce management."
            )
        )
    except Exception as e:
        logging.error("Schedule change request failed: %s", e)
        call.hangup(
            final_instructions=(
                f"Apologize to {first_name} for a technical issue and let them know their "
                f"{request_type} request for {date_display} could not be submitted right now. "
                "Ask them to try again through the Calabrio portal or contact their supervisor "
                "directly. Thank them for their patience."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
