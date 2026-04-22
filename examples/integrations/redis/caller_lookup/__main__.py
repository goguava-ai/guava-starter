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


agent = guava.Agent(
    name="Casey",
    organization="Crestwood Support",
    purpose=(
        "to provide fast, personalized support to Crestwood customers "
        "by recognizing returning callers and picking up where they left off"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    # Look up the caller's phone number from the inbound call metadata.
    caller_phone = call.get_caller_number() or ""
    call.caller_phone = caller_phone
    call.profile = get_caller_profile(caller_phone) if caller_phone else None

    if call.profile:
        logging.info("Returning caller recognized: %s (%s)", call.profile.get("name"), caller_phone)
    else:
        logging.info("New caller from %s — no cached profile found.", caller_phone)

    if call.profile:
        name = call.profile.get("name", "there")
        last_topic = call.profile.get("last_topic", "")
        topic_mention = f" Last time you called about {last_topic}." if last_topic else ""

        call.set_task(
            "wrap_up",
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
        )
    else:
        call.set_task(
            "wrap_up",
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
        )


@agent.on_task_complete("wrap_up")
def on_done(call: guava.Call) -> None:
    today_request = call.get_field("today_request") or ""
    resolution = call.get_field("resolution") or ""

    if call.profile:
        name = call.profile.get("name", "")
        updated_profile = {
            **call.profile,
            "last_topic": today_request[:120],
            "call_count": call.profile.get("call_count", 1) + 1,
        }
    else:
        name = call.get_field("caller_name") or ""
        updated_profile = {
            "name": name,
            "phone": call.caller_phone,
            "last_topic": today_request[:120],
            "call_count": 1,
        }

    if call.caller_phone:
        try:
            save_caller_profile(call.caller_phone, updated_profile)
            logging.info("Caller profile saved/updated for %s.", call.caller_phone)
        except Exception as e:
            logging.error("Failed to save caller profile to Redis: %s", e)

    call.hangup(
        final_instructions=(
            f"Confirm the resolution with {name or 'the caller'}: {resolution}. "
            "Thank them for calling Crestwood Support and wish them a great day."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
