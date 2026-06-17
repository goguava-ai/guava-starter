# SDK conformance: guava-sdk 0.29.0 (2026-06-16)
"""Plug a raw Google GenAI (Gemini) client into Guava callbacks.

This example shows how to integrate your own Gemini key (and your own model
choice / prompt / schema) with guava.

For the simpler Guava-key-only path (no Gemini credentials needed), use
the functions provided in guava.helpers.llm.
"""

import argparse
import os
from datetime import date
from typing import Literal

import guava
from google import genai
from guava import logging_utils
from pydantic import BaseModel, ConfigDict

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")

# Reads GOOGLE_API_KEY from the environment by default.
# For Vertex AI, pass vertexai=True, project=..., location=...
client = genai.Client(vertexai=True)


# ── Mock data ────────────────────────────────────────────────────────────────

INTENTS = {
    "wait time": "How long until a table is open?",
    "reservation": "Book a table for a future date and time.",
    "anything else": "Any other request.",
}

# Pretend these came from a real reservation system.
AVAILABLE_SLOTS = [
    "2026-05-12T18:00",
    "2026-05-12T18:30",
    "2026-05-12T19:00",
    "2026-05-13T19:30",
    "2026-05-13T20:00",
    "2026-05-14T18:00",
]


# ── Pydantic schemas constraining the model output ───────────────────────────


class _IntentChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intent: Literal["wait time", "reservation", "anything else"]


class _SlotMatches(BaseModel):
    model_config = ConfigDict(extra="forbid")
    matching: list[str]
    fallback: list[str]


# ── Gemini calls (inline in the user's callbacks) ────────────────────────────


def classify_intent_via_gemini(utterance: str) -> str:
    """Pick the closest intent from INTENTS for the caller's utterance."""
    descriptions = "\n".join(f"  {k}: {v}" for k, v in INTENTS.items())
    prompt = (
        "Pick the choice that best matches the caller's intent.\n\n"
        f"Caller said: {utterance!r}\n\n"
        f"Choices:\n{descriptions}"
    )
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "response_json_schema": _IntentChoice.model_json_schema(),
        },
    )
    assert response.text
    return _IntentChoice.model_validate_json(response.text).intent


def filter_slots_via_gemini(query: str) -> tuple[list[str], list[str]]:
    """Return (matching, fallback) slots for the caller's natural-language query."""
    slot_list = "\n".join(AVAILABLE_SLOTS)
    prompt = (
        "Return slots from the list that match the caller's request.\n"
        "If none match, return close alternatives in `fallback` instead.\n"
        "Never return slots that are not in the list.\n\n"
        f"Today: {date.today():%B %d, %Y}\n"
        f"Caller said: {query!r}\n\n"
        f"Available slots:\n{slot_list}\n\n"
        "Return at most 3 items per list."
    )
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "response_json_schema": _SlotMatches.model_json_schema(),
        },
    )
    assert response.text
    parsed = _SlotMatches.model_validate_json(response.text)
    return parsed.matching[:3], parsed.fallback[:3]


# ── Guava controller ─────────────────────────────────────────────────────────


agent = guava.Agent(
    name="Grace",
    organization="Thai Palace",
    purpose="Take reservations and route inbound calls.",
)


@agent.on_call_received
def on_call_received(_: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task("intro", "Greet the caller and figure out why they're calling.")


@agent.on_action_request
def on_action_request(_: guava.Call, request: str) -> guava.SuggestedAction | None:
    """Use raw Gemini to map the caller's request to one of our intents."""
    intent = classify_intent_via_gemini(request)
    return guava.SuggestedAction(key=intent, description=INTENTS[intent])


@agent.on_action("wait time")
def wait_time(call: guava.Call):
    call.hangup("Tell the caller the current wait time is about 25 minutes.")


@agent.on_action("reservation")
def reservation(call: guava.Call):
    call.set_task(
        "book_reservation",
        "Find a reservation time that works for the caller.",
        checklist=[
            guava.Field(
                key="reservation_time",
                field_type="calendar_slot",
                description="Ask when they'd like to dine. Offer 2–3 options.",
                searchable=True,
                required=True,
            ),
            "Confirm the reservation time and end the call.",
        ],
    )


@agent.on_search_query("reservation_time")
def search_reservation_slots(_: guava.Call, query: str):
    """Use raw Gemini to filter the available slot list against natural language."""
    return filter_slots_via_gemini(query)


@agent.on_action("anything else")
def fallback(call: guava.Call):
    call.hangup("Apologize and let the caller know we're unable to help with that.")


if __name__ == "__main__":
    logging_utils.configure_logging()

    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--phone", metavar="PHONE_NUMBER", nargs="?", const="", help="Listen for phone calls."
    )
    group.add_argument(
        "--webrtc", metavar="WEBRTC_CODE", nargs="?", const="", help="Listen on a WebRTC code."
    )
    group.add_argument("--local", action="store_true", help="Start a local call.")
    group.add_argument("--sip", metavar="SIP_CODE", help="Listen on a SIP code 'guavasip-...'.")
    args = parser.parse_args()

    if args.phone is not None:
        agent.listen_phone(args.phone)
    elif args.webrtc is not None:
        agent.listen_webrtc(args.webrtc or None)
    elif args.sip:
        agent.listen_sip(args.sip)
    else:
        agent.call_local()
