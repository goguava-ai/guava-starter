import guava
import os
import logging
from guava import logging_utils
import json
import redis


r = redis.Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)

CALLER_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days


def get_caller_profile(phone: str) -> dict | None:
    """Fetches a cached caller profile from Redis. Returns None if not found."""
    key = f"caller:{phone}"
    raw = r.get(key)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def save_caller_profile(phone: str, profile: dict) -> None:
    """Persists a caller profile to Redis with a 30-day TTL."""
    key = f"caller:{phone}"
    r.setex(key, CALLER_TTL_SECONDS, json.dumps(profile))


class CallerLookupController(guava.CallController):
    def __init__(self):
        super().__init__()

        # Look up the caller's phone number from the inbound call metadata.
        caller_phone = self.get_caller_number() or ""
        self.caller_phone = caller_phone
        self.profile = get_caller_profile(caller_phone) if caller_phone else None

        if self.profile:
            logging.info("Returning caller recognized: %s (%s)", self.profile.get("name"), caller_phone)
        else:
            logging.info("New caller from %s — no cached profile found.", caller_phone)

        self.set_persona(
            organization_name="Crestwood Support",
            agent_name="Casey",
            agent_purpose=(
                "to provide fast, personalized support to Crestwood customers "
                "by recognizing returning callers and picking up where they left off"
            ),
        )

        if self.profile:
            self._start_returning_caller_flow()
        else:
            self._start_new_caller_flow()

    def _start_returning_caller_flow(self):
        name = self.profile.get("name", "there")
        last_topic = self.profile.get("last_topic", "")
        topic_mention = f" Last time you called about {last_topic}." if last_topic else ""

        self.set_task(
            objective=(
                f"Welcome back {name} as a returning caller. Acknowledge their history "
                "and quickly understand how to help them today."
            ),
            checklist=[
                guava.Say(
                    f"Welcome back to Crestwood Support, {name}! This is Casey.{topic_mention} "
                    "How can I help you today?"
                ),
                guava.Field(
                    key="today_request",
                    field_type="text",
                    description="Let the caller describe what they need help with today.",
                    required=True,
                ),
                guava.Field(
                    key="resolution",
                    field_type="text",
                    description=(
                        "Assist the caller with their request. Once resolved, confirm the outcome "
                        "in a sentence."
                    ),
                    required=True,
                ),
            ],
            on_complete=self.wrap_up,
        )

        self.accept_call()

    def _start_new_caller_flow(self):
        self.set_task(
            objective=(
                "A new caller has reached Crestwood Support. Greet them, collect their name "
                "and reason for calling, assist them, and save their profile for future calls."
            ),
            checklist=[
                guava.Say(
                    "Thanks for calling Crestwood Support. I'm Casey — happy to help. "
                    "Could I start with your name?"
                ),
                guava.Field(
                    key="caller_name",
                    field_type="text",
                    description="Ask for the caller's full name.",
                    required=True,
                ),
                guava.Field(
                    key="today_request",
                    field_type="text",
                    description="Ask what they're calling about today.",
                    required=True,
                ),
                guava.Field(
                    key="resolution",
                    field_type="text",
                    description=(
                        "Assist the caller with their request. Summarize the resolution in a sentence."
                    ),
                    required=True,
                ),
            ],
            on_complete=self.wrap_up,
        )

        self.accept_call()

    def wrap_up(self):
        today_request = self.get_field("today_request") or ""
        resolution = self.get_field("resolution") or ""

        if self.profile:
            name = self.profile.get("name", "")
            updated_profile = {
                **self.profile,
                "last_topic": today_request[:120],
                "call_count": self.profile.get("call_count", 1) + 1,
            }
        else:
            name = self.get_field("caller_name") or ""
            updated_profile = {
                "name": name,
                "phone": self.caller_phone,
                "last_topic": today_request[:120],
                "call_count": 1,
            }

        if self.caller_phone:
            try:
                save_caller_profile(self.caller_phone, updated_profile)
                logging.info("Caller profile saved/updated for %s.", self.caller_phone)
            except Exception as e:
                logging.error("Failed to save caller profile to Redis: %s", e)

        self.hangup(
            final_instructions=(
                f"Confirm the resolution with {name or 'the caller'}: {resolution}. "
                "Thank them for calling Crestwood Support and wish them a great day."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=CallerLookupController,
    )
