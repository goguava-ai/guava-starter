import guava
import os
import logging
import redis
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)

r = redis.Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)

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


class CallDedupController(guava.CallController):
    def __init__(self):
        super().__init__()

        caller_phone = self.get_caller_number() or ""
        self.caller_phone = caller_phone
        self.is_repeat = is_repeat_caller(caller_phone) if caller_phone else False
        self.call_count = get_call_count(caller_phone) if caller_phone else 1

        if caller_phone:
            mark_caller(caller_phone)

        logging.info(
            "Caller %s — repeat within window: %s, lifetime calls: %d",
            caller_phone, self.is_repeat, self.call_count,
        )

        self.set_persona(
            organization_name="Ironhull Support",
            agent_name="Morgan",
            agent_purpose="to provide support to Ironhull customers efficiently and without unnecessary repetition",
        )

        if self.is_repeat:
            self._handle_repeat_caller()
        else:
            self._handle_new_call()

    def _handle_repeat_caller(self):
        window_minutes = DEDUP_WINDOW_SECONDS // 60

        self.set_task(
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
            on_complete=self.handle_repeat_outcome,
        )

        self.accept_call()

    def _handle_new_call(self):
        self.set_task(
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
            on_complete=self.handle_new_call_outcome,
        )

        self.accept_call()

    def handle_repeat_outcome(self):
        status = self.get_field("issue_status") or "still unresolved"
        detail = self.get_field("issue_detail") or ""
        escalate = self.get_field("escalate") or "no, just help me here"

        logging.info(
            "Repeat caller %s — status: %s, escalate: %s", self.caller_phone, status, escalate,
        )

        if escalate == "yes, escalate":
            self.hangup(
                final_instructions=(
                    "Let the caller know they're being escalated to a senior support specialist "
                    "who will call them back within 15 minutes. Apologize for the inconvenience "
                    "and thank them for their patience. Be empathetic and reassuring."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    "Address the caller's issue directly based on what they described. "
                    f"Their situation: {detail}. "
                    "Do your best to resolve it or set a clear expectation on next steps. "
                    "Thank them for their patience and wish them a good day."
                )
            )

    def handle_new_call_outcome(self):
        name = self.get_field("caller_name") or "there"
        resolution = self.get_field("resolution") or ""

        logging.info("Call resolved for %s (%s).", name, self.caller_phone)

        self.hangup(
            final_instructions=(
                f"Confirm the resolution with {name}: {resolution}. "
                "Thank them for calling Ironhull Support and wish them a great day."
            )
        )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=CallDedupController,
    )
