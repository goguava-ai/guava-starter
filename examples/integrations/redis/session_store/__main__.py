import guava
import os
import logging
import json
import redis
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)

r = redis.Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)

SESSION_TTL_SECONDS = int(os.environ.get("SESSION_TTL_SECONDS", 3600))  # 1 hour default


def save_session(session_id: str, data: dict) -> None:
    """Persists call session data to Redis with a TTL."""
    key = f"call_session:{session_id}"
    r.setex(key, SESSION_TTL_SECONDS, json.dumps(data))


def get_session(session_id: str) -> dict | None:
    key = f"call_session:{session_id}"
    raw = r.get(key)
    return json.loads(raw) if raw else None


def publish_session_event(session_id: str, event: str, data: dict) -> None:
    """Publishes a call event to a Redis Pub/Sub channel for real-time subscribers."""
    channel = f"call_events:{session_id}"
    message = json.dumps({"event": event, "data": data, "ts": datetime.now(timezone.utc).isoformat()})
    r.publish(channel, message)


class SessionStoreController(guava.CallController):
    def __init__(self):
        super().__init__()

        # Use the inbound call's caller number + timestamp as the session ID.
        caller_phone = self.get_caller_number() or "unknown"
        self.session_id = f"{caller_phone.lstrip('+')}-{int(datetime.utcnow().timestamp())}"

        logging.info("Call session started: %s", self.session_id)

        # Publish a session-started event so real-time subscribers can react.
        try:
            publish_session_event(self.session_id, "call_started", {"phone": caller_phone})
        except Exception as e:
            logging.warning("Could not publish call_started event: %s", e)

        self.set_persona(
            organization_name="Skyline Financial",
            agent_name="Casey",
            agent_purpose=(
                "to assist Skyline Financial customers and securely capture their collected data "
                "so downstream systems can process it in real time"
            ),
        )

        self.set_task(
            objective=(
                "Assist the caller with their financial account inquiry. Store all collected data "
                "in Redis so it can be picked up immediately by the processing pipeline."
            ),
            checklist=[
                guava.Say(
                    "Thanks for calling Skyline Financial. I'm Casey. "
                    "I'll ask you a few questions and get you sorted right away."
                ),
                guava.Field(
                    key="caller_name",
                    field_type="text",
                    description="Ask for the caller's full name.",
                    required=True,
                ),
                guava.Field(
                    key="account_number",
                    field_type="text",
                    description="Ask for their account number. Repeat it back to confirm.",
                    required=True,
                ),
                guava.Field(
                    key="request_type",
                    field_type="multiple_choice",
                    description="Ask what they'd like help with.",
                    choices=[
                        "account balance inquiry",
                        "transaction dispute",
                        "statement request",
                        "transfer request",
                        "account update",
                        "other",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="request_detail",
                    field_type="text",
                    description=(
                        "Ask them to describe their request in detail. "
                        "Capture everything relevant."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="preferred_followup",
                    field_type="multiple_choice",
                    description="Ask how they'd like to be followed up with if needed.",
                    choices=["email", "phone call", "secure message in app"],
                    required=True,
                ),
            ],
            on_complete=self.persist_and_close,
        )

        self.accept_call()

    def persist_and_close(self):
        name = self.get_field("caller_name") or "Unknown"
        account_number = self.get_field("account_number") or ""
        request_type = self.get_field("request_type") or ""
        detail = self.get_field("request_detail") or ""
        followup = self.get_field("preferred_followup") or "email"

        session_data = {
            "session_id": self.session_id,
            "caller_name": name,
            "account_number": account_number,
            "request_type": request_type,
            "request_detail": detail,
            "preferred_followup": followup,
            "call_started_at": datetime.now(timezone.utc).isoformat(),
        }

        logging.info("Saving session %s to Redis for account %s.", self.session_id, account_number)
        try:
            save_session(self.session_id, session_data)
            logging.info("Session %s saved (TTL: %ds).", self.session_id, SESSION_TTL_SECONDS)
        except Exception as e:
            logging.error("Failed to save session to Redis: %s", e)

        try:
            publish_session_event(self.session_id, "call_completed", session_data)
            logging.info("call_completed event published for session %s.", self.session_id)
        except Exception as e:
            logging.warning("Could not publish call_completed event: %s", e)

        self.hangup(
            final_instructions=(
                f"Thank {name} for calling Skyline Financial. Let them know their request has been "
                f"captured and will be processed. They'll be followed up with via {followup}. "
                "Wish them a great day."
            )
        )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=SessionStoreController,
    )
