import logging
import os
from datetime import datetime, timezone

import guava
from guava import logging_utils
from redis import Redis

r = Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)

# Callers are considered repeat within this window (in seconds).
DEDUP_WINDOW_SECONDS = int(os.environ.get("DEDUP_WINDOW_SECONDS", 300))  # 5 minutes default


def is_repeat_caller(phone: str) -> bool:
    """Returns True if the caller has called within the dedup window."""
    key = f"recent_call:{phone}"
    return r.exists(key) == 1


def mark_caller(phone: str) -> None:
    """Sets a Redis key for the caller that expires after the dedup window."""
    key = f"recent_call:{phone}"
    r.setex(key, DEDUP_WINDOW_SECONDS, datetime.now(timezone.utc).isoformat())


def get_call_count(phone: str) -> int:
    """Returns the lifetime call count for this phone number."""
    key = f"call_count:{phone}"
    count = r.incr(key)
    # Set a 1-year expiry on first creation
    if count == 1:
        r.expire(key, 60 * 60 * 24 * 365)
    return count


agent = guava.Agent(
    name="Morgan",
    organization="Ironhull Support",
    purpose="to provide support to Ironhull customers efficiently and without unnecessary repetition",
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    caller_phone = call.get_variable("caller_phone") or ""
    is_repeat = is_repeat_caller(caller_phone) if caller_phone else False
    call_count = get_call_count(caller_phone) if caller_phone else 1

    if caller_phone:
        mark_caller(caller_phone)

    call.set_variable("caller_phone", caller_phone)

    logging.info(
        "Caller %s — repeat within window: %s, lifetime calls: %d",
        caller_phone, is_repeat, call_count,
    )

    if is_repeat:
        window_minutes = DEDUP_WINDOW_SECONDS // 60

        call.set_task(
            "handle_repeat_outcome",
            objective=(
                "This caller has called multiple times within a short window. "
                "Acknowledge this empathetically, understand if their previous issue wasn't resolved, "
                "and escalate or prioritize accordingly."
            ),
            checklist=[
                guava.Say(
                    "Hi, thanks for calling Ironhull Support again. I'm Morgan. "
                    "I see you've reached out recently — I want to make sure we get "
                    "this sorted for you properly this time."
                ),
                guava.Field(
                    key="issue_status",
                    field_type="multiple_choice",
                    description=(
                        "Ask if their previous issue was resolved or if they're still experiencing "
                        "the same problem."
                    ),
                    choices=["still unresolved", "new issue", "just following up"],
                    required=True,
                ),
                guava.Field(
                    key="issue_detail",
                    field_type="text",
                    description=(
                        "Ask them to describe the issue or what they need right now. "
                        "Capture the full detail."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="escalate",
                    field_type="multiple_choice",
                    description=(
                        "Given they're calling again, ask if they'd like to be connected with "
                        "a senior support specialist directly."
                    ),
                    choices=["yes, escalate", "no, just help me here"],
                    required=True,
                ),
            ],
        )
    else:
        call.set_task(
            "handle_new_call_outcome",
            objective=(
                "A caller has reached Ironhull Support. Greet them, understand their issue, "
                "and assist them."
            ),
            checklist=[
                guava.Say(
                    "Thanks for calling Ironhull Support. I'm Morgan — happy to help. "
                    "What can I assist you with today?"
                ),
                guava.Field(
                    key="caller_name",
                    field_type="text",
                    description="Ask for their name.",
                    required=True,
                ),
                guava.Field(
                    key="issue_detail",
                    field_type="text",
                    description="Ask them to describe their issue or question.",
                    required=True,
                ),
                guava.Field(
                    key="resolution",
                    field_type="text",
                    description=(
                        "Assist the caller with their issue. Capture a brief summary of the "
                        "resolution or next step."
                    ),
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("handle_repeat_outcome")
def on_repeat_done(call: guava.Call) -> None:
    status = call.get_field("issue_status") or "still unresolved"
    detail = call.get_field("issue_detail") or ""
    escalate = call.get_field("escalate") or "no, just help me here"

    logging.info(
        "Repeat caller %s — status: %s, escalate: %s", call.get_variable("caller_phone"), status, escalate,
    )

    if escalate == "yes, escalate":
        call.hangup(
            final_instructions=(
                "Let the caller know they're being escalated to a senior support specialist "
                "who will call them back within 15 minutes. Apologize for the inconvenience "
                "and thank them for their patience. Be empathetic and reassuring."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                "Address the caller's issue directly based on what they described. "
                f"Their situation: {detail}. "
                "Do your best to resolve it or set a clear expectation on next steps. "
                "Thank them for their patience and wish them a good day."
            )
        )


@agent.on_task_complete("handle_new_call_outcome")
def on_new_done(call: guava.Call) -> None:
    name = call.get_field("caller_name") or "there"
    resolution = call.get_field("resolution") or ""

    logging.info("Call resolved for %s (%s).", name, call.get_variable("caller_phone"))

    call.hangup(
        final_instructions=(
            f"Confirm the resolution with {name}: {resolution}. "
            "Thank them for calling Ironhull Support and wish them a great day."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
