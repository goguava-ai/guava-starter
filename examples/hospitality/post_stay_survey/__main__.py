# SDK conformance: guava-sdk 0.42.0 (2026-09-08)
import argparse
import json
import logging
import os
from datetime import datetime, timezone

import guava
from guava import logging_utils
from guava.helpers.llm import IntentRecognizer
from guava.events import BotSessionEnded, OutboundCallFailed

agent = guava.Agent(
    name="Noel",
    organization="The Grand Meridian Hotel",
    purpose=(
        "follow up with recent guests to gather honest feedback about their "
        "stay, celebrate what went well, and understand where the hotel can "
        "improve"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
    "speak_to_someone": "The caller wants to speak to a manager, front desk, or real person",
})


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(
        contact_full_name=call.get_variable("guest_name"),
        voicemail_message=(
            f"Hi, this is Noel from The Grand Meridian Hotel calling for "
            f"{call.get_variable('guest_name')}. We'd love to hear about your "
            f"recent stay. Please call us back at your convenience. Thank you!"
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    guest_name = call.get_variable("guest_name")
    checkout_date = call.get_variable("checkout_date")
    reservation_number = call.get_variable("reservation_number")

    if outcome == "available":
        call.set_task(
            "survey",
            objective=(
                f"Conduct a warm, conversational post-stay survey with "
                f"{guest_name} following their checkout on {checkout_date} "
                f"(reservation {reservation_number}). Collect ratings for "
                f"overall stay, room cleanliness, staff service, and amenities "
                f"on a 1-to-5 scale. If any rating is 2 or below, probe for "
                f"what could be improved. Flag any safety or cleanliness "
                f"concerns for manager review."
            ),
            checklist=[
                guava.Say(
                    "Thank you so much for staying with us. I'd love to hear "
                    "how your experience was — this should only take a couple "
                    "of minutes."
                ),
                guava.Field(
                    key="overall_rating",
                    description=(
                        "On a scale of 1 to 5, with 5 being exceptional, how "
                        "would the guest rate their overall stay?"
                    ),
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="cleanliness_rating",
                    description=(
                        "On a scale of 1 to 5, how would the guest rate the "
                        "cleanliness of their room?"
                    ),
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="staff_rating",
                    description=(
                        "On a scale of 1 to 5, how would the guest rate the "
                        "attentiveness and professionalism of the staff?"
                    ),
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="amenities_rating",
                    description=(
                        "On a scale of 1 to 5, how would the guest rate the "
                        "hotel amenities such as restaurant, spa, fitness center, "
                        "or pool?"
                    ),
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="highlights",
                    description=(
                        "Any standout moments or highlights from the guest's stay"
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="areas_for_improvement",
                    description=(
                        "Anything the hotel could have done differently to make "
                        "the experience even better"
                    ),
                    field_type="text",
                    required=False,
                ),
            ],
        )
    elif outcome == "do_not_contact":
        logging.info("Guest %s requested no further contact.", guest_name)
        call.hangup(
            final_instructions=(
                "Acknowledge their request graciously. Let them know they will "
                "not be contacted again, and wish them well, and politely say goodbye."
            )
        )
    elif outcome == "wrong_number":
        logging.info("Wrong number for %s.", guest_name)
        call.hangup(final_instructions="Apologize for the mistake and wish them well, and politely say goodbye.")
    else:
        logging.info("Could not reach %s (outcome: %s).", guest_name, outcome)
        call.hangup()


@agent.on_task_complete("survey")
def on_survey_done(call: guava.Call) -> None:
    guest_name = call.get_variable("guest_name")
    overall = call.get_field("overall_rating")
    cleanliness = call.get_field("cleanliness_rating")
    staff = call.get_field("staff_rating")
    improvement = call.get_field("areas_for_improvement")

    # Check for critical feedback (safety/cleanliness concerns)
    has_critical = False
    if isinstance(cleanliness, int) and cleanliness <= 2:
        has_critical = True
    if improvement and any(
        word in str(improvement).lower()
        for word in ["safety", "unsafe", "hazard", "dirty", "mold", "pest", "bug"]
    ):
        has_critical = True

    # Branch on low scores for follow-up probe
    low_scores = []
    if isinstance(overall, int) and overall <= 2:
        low_scores.append("overall")
    if isinstance(cleanliness, int) and cleanliness <= 2:
        low_scores.append("cleanliness")
    if isinstance(staff, int) and staff <= 2:
        low_scores.append("staff")

    if low_scores:
        call.set_task(
            "low_score_followup",
            objective=(
                f"{guest_name} gave low ratings in: {', '.join(low_scores)}. "
                f"Ask what specifically went wrong and what the hotel could have "
                f"done better. Listen with genuine empathy. Let them know their "
                f"feedback will be reviewed by the hotel management team."
            ),
            checklist=[
                guava.Field(
                    key="low_score_detail",
                    description="Specific details about what went wrong for the low-rated areas",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="would_return",
                    description="Whether the guest would consider returning to The Grand Meridian in the future",
                    field_type="multiple_choice",
                    choices=["yes", "no", "maybe"],
                    required=True,
                ),
            ],
        )
    else:
        if has_critical:
            logging.warning(
                "CRITICAL FEEDBACK flagged for manager review — guest: %s",
                guest_name,
            )
        call.hangup(
            final_instructions=(
                f"Thank {guest_name} sincerely for their feedback. Let them "
                f"know their responses will be shared with the hotel leadership "
                f"team. Express hope to welcome them back in the future, and politely say goodbye."
            )
        )


@agent.on_task_complete("low_score_followup")
def on_low_score_done(call: guava.Call) -> None:
    guest_name = call.get_variable("guest_name")
    logging.warning(
        "Low-score feedback collected from %s — flagged for manager review.",
        guest_name,
    )
    call.hangup(
        final_instructions=(
            f"Thank {guest_name} genuinely for sharing that feedback — it helps "
            f"the team improve. Assure them their concerns will be reviewed by "
            f"hotel management. If they expressed interest in returning, let them "
            f"know the hotel would love to make their next visit exceptional. "
            f"Wish them well, and politely say goodbye."
        )
    )


@agent.on_action_request
def on_action_request(call: guava.Call, intent_summary: str):
    return _mid_call_intent.classify(intent_summary)


@agent.on_action("do_not_contact")
def handle_dnc(call: guava.Call) -> None:
    logging.info("Guest %s requested DNC mid-call.", call.get_variable("guest_name"))
    call.hangup(
        final_instructions=(
            "Acknowledge their request. Let them know they have been removed "
            "from the contact list and will not be called again, and wish them well, and politely say goodbye."
        )
    )


@agent.on_action("speak_to_someone")
def handle_speak_to_someone(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            "Let them know that a member of the hotel management team will "
            "reach out within one business day. Ask if there is a preferred "
            "time and thank them, and politely say goodbye."
        )
    )


@agent.on_outbound_failed
def on_outbound_failed(event: OutboundCallFailed) -> None:
    logging.error("Outbound call failed: %s (code %d)", event.error_reason, event.error_code)


@agent.on_session_end
def on_session_end(call: guava.Call, event: BotSessionEnded) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "use_case": "post_stay_survey",
        "guest_name": call.get_variable("guest_name"),
        "reservation_number": call.get_variable("reservation_number"),
        "checkout_date": call.get_variable("checkout_date"),
        "overall_rating": call.get_field("overall_rating"),
        "cleanliness_rating": call.get_field("cleanliness_rating"),
        "staff_rating": call.get_field("staff_rating"),
        "amenities_rating": call.get_field("amenities_rating"),
        "highlights": call.get_field("highlights"),
        "areas_for_improvement": call.get_field("areas_for_improvement"),
        "low_score_detail": call.get_field("low_score_detail"),
        "would_return": call.get_field("would_return"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound post-stay survey call — The Grand Meridian Hotel"
    )
    parser.add_argument("phone", help="Guest phone number to call")
    parser.add_argument("--name", required=True, help="Full name of the guest")
    parser.add_argument("--reservation-number", required=True, help="Reservation reference number")
    parser.add_argument("--checkout-date", required=True, help="Date the guest checked out")
    parser.add_argument(
        "--from-number",
        default=os.environ.get("GUAVA_AGENT_NUMBER", ""),
        help="Caller ID / from number (defaults to GUAVA_AGENT_NUMBER env var).",
    )
    args = parser.parse_args()

    agent.call_phone(
        from_number=args.from_number,
        to_number=args.phone,
        variables={
            "guest_name": args.name,
            "reservation_number": args.reservation_number,
            "checkout_date": args.checkout_date,
        },
    )
