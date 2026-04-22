import guava
import os
import logging
from guava import logging_utils
import json
from redis import Redis
from datetime import datetime, timezone


r = Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)

CALLBACK_QUEUE_KEY = os.environ.get("CALLBACK_QUEUE_KEY", "guava:callback_queue")


def enqueue_callback(phone: str, name: str, issue: str, priority: str) -> int:
    """Pushes a callback request onto the Redis list. Returns the new queue length."""
    record = json.dumps({
        "phone": phone,
        "name": name,
        "issue": issue,
        "priority": priority,
        "queued_at": datetime.now(timezone.utc).isoformat(),
    })
    # High-priority callers go to the front of the queue (LPUSH), others to the back (RPUSH).
    if priority == "high":
        return r.lpush(CALLBACK_QUEUE_KEY, record)
    return r.rpush(CALLBACK_QUEUE_KEY, record)


def get_queue_length() -> int:
    return r.llen(CALLBACK_QUEUE_KEY)


agent = guava.Agent(
    name="Sam",
    organization="Meridian Help Desk",
    purpose=(
        "to help Meridian Help Desk callers when wait times are long — "
        "capturing their details and adding them to the callback queue so an agent "
        "can call them back instead of having them wait on hold"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    queue_depth = get_queue_length()

    call.set_task(
        "add_to_queue",
        objective=(
            "An incoming caller has been offered a callback because agents are currently busy. "
            "Confirm they'd like a callback, collect their name and issue, and add them to "
            "the callback queue in Redis."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Meridian Help Desk. All of our agents are currently "
                "assisting other customers. Rather than having you wait on hold, I can add you "
                "to our callback queue and an agent will call you back shortly."
            ),
            guava.Field(
                key="wants_callback",
                field_type="multiple_choice",
                description="Ask if they'd like to be added to the callback queue.",
                choices=["yes", "no, I'll hold"],
                required=True,
            ),
            guava.Field(
                key="caller_name",
                field_type="text",
                description="Ask for their full name so the agent knows who they're calling.",
                required=True,
            ),
            guava.Field(
                key="callback_number",
                field_type="text",
                description=(
                    "Ask for the best phone number to call them back. "
                    "Confirm it back to them."
                ),
                required=True,
            ),
            guava.Field(
                key="issue_summary",
                field_type="text",
                description=(
                    "Ask for a brief description of what they need help with, "
                    "so the agent can prepare before calling."
                ),
                required=True,
            ),
            guava.Field(
                key="priority",
                field_type="multiple_choice",
                description=(
                    "Ask how urgent this is for them so we can prioritize the queue."
                ),
                choices=["high — urgent issue", "normal — not urgent"],
                required=True,
            ),
        ],
    )


@agent.on_task_complete("add_to_queue")
def on_done(call: guava.Call) -> None:
    wants_callback = call.get_field("wants_callback") or "yes"
    name = call.get_field("caller_name") or "Unknown"
    callback_number = call.get_field("callback_number") or call.get_variable("caller_phone") or ""
    issue = call.get_field("issue_summary") or ""
    priority_raw = call.get_field("priority") or "normal — not urgent"
    priority = "high" if "high" in priority_raw else "normal"

    if wants_callback == "no, I'll hold":
        call.hangup(
            final_instructions=(
                f"Let {name} know you're transferring them to the hold queue and an agent "
                "will be with them as soon as possible. Apologize for the wait and thank "
                "them for their patience."
            )
        )
        return

    logging.info(
        "Adding %s (%s) to callback queue — priority: %s", name, callback_number, priority,
    )

    try:
        queue_position = enqueue_callback(callback_number, name, issue, priority)
        logging.info(
            "Callback queued for %s — position %d in queue.", name, queue_position,
        )
        call.hangup(
            final_instructions=(
                f"Confirm to {name} that they've been added to the callback queue "
                f"and are number {queue_position} in line. "
                "Let them know an agent will call them back at the number they provided. "
                + ("Since they marked it as urgent, let them know they've been prioritized. "
                   if priority == "high" else "")
                + "Thank them for their patience and wish them a good day."
            )
        )
    except Exception as e:
        logging.error("Failed to enqueue callback for %s: %s", name, e)
        call.hangup(
            final_instructions=(
                f"Apologize to {name} for a technical issue. Let them know an agent will "
                "attempt to call them back manually as soon as possible. Thank them for their patience."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
