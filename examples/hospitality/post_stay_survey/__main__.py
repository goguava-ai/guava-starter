import guava
import os
import logging
from guava import logging_utils
import json
import argparse
from datetime import datetime, timezone


agent = guava.Agent(
    name="Sophie",
    organization="The Grand Meridian Hotel",
    purpose=(
        "follow up with a recent guest to gather honest feedback about their stay, "
        "celebrate what went well, and understand where the hotel can do even better"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(contact_full_name=call.get_variable("name"))


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    if outcome == "unavailable":
        logging.warning("Could not reach %s for post-stay survey.", call.get_variable("name"))
        call.hangup(
            final_instructions=(
                "Leave a warm voicemail as Sophie from The Grand Meridian Hotel, thanking the guest "
                "for their recent stay and letting them know you were hoping to gather a few minutes "
                "of feedback. Invite them to call back or reach out via the hotel's website if they "
                "would like to share their experience."
            )
        )
    elif outcome == "available":
        call.set_task(
            "survey",
            objective=(
                f"You are following up with {call.get_variable('name')} following their checkout on {call.get_variable('checkout_date')} "
                f"(reservation {call.get_variable('reservation_number')}). Conduct a warm, conversational post-stay survey. "
                "Collect numerical ratings on a scale of 1 to 5 for overall stay, room cleanliness, "
                "staff service, and amenities. Also ask whether they would return, invite them to share "
                "highlights, and ask about any areas for improvement. Be gracious and genuinely appreciative "
                "of their feedback — every response helps the hotel maintain its commitment to excellence."
            ),
            checklist=[
                guava.Say(
                    f"Thank {call.get_variable('name')} warmly for choosing The Grand Meridian Hotel and for taking "
                    f"a moment to share feedback about their stay, which ended on {call.get_variable('checkout_date')}. "
                    "Explain that the survey takes only a couple of minutes and that their insights are "
                    "deeply valued by the entire hotel team."
                ),
                guava.Field(
                    key="overall_stay_rating",
                    description=(
                        "On a scale of 1 to 5, with 5 being exceptional, how would the guest "
                        "rate their overall stay at The Grand Meridian Hotel?"
                    ),
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="room_cleanliness_rating",
                    description=(
                        "On a scale of 1 to 5, how would the guest rate the cleanliness "
                        "and presentation of their room?"
                    ),
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="staff_service_rating",
                    description=(
                        "On a scale of 1 to 5, how would the guest rate the attentiveness "
                        "and professionalism of the hotel staff?"
                    ),
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="amenities_rating",
                    description=(
                        "On a scale of 1 to 5, how would the guest rate the hotel's amenities, "
                        "such as the restaurant, spa, fitness centre, or pool?"
                    ),
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="would_return",
                    description="Would the guest consider returning to The Grand Meridian Hotel for a future stay?",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="highlights",
                    description=(
                        "Were there any particular highlights or standout moments during the guest's "
                        "stay that they would like to mention?"
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="areas_for_improvement",
                    description=(
                        "Is there anything the hotel could have done differently to make "
                        "the guest's experience even better?"
                    ),
                    field_type="text",
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("survey")
def on_done(call: guava.Call) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "use_case": "post_stay_survey",
        "guest_name": call.get_variable("name"),
        "reservation_number": call.get_variable("reservation_number"),
        "checkout_date": call.get_variable("checkout_date"),
        "fields": {
            "overall_stay_rating": call.get_field("overall_stay_rating"),
            "room_cleanliness_rating": call.get_field("room_cleanliness_rating"),
            "staff_service_rating": call.get_field("staff_service_rating"),
            "amenities_rating": call.get_field("amenities_rating"),
            "would_return": call.get_field("would_return"),
            "highlights": call.get_field("highlights"),
            "areas_for_improvement": call.get_field("areas_for_improvement"),
        },
    }
    print(json.dumps(results, indent=2))
    logging.info("Post-stay survey results saved for %s", call.get_variable("name"))
    call.hangup(
        final_instructions=(
            f"Thank {call.get_variable('name')} sincerely for their candid feedback and for being a valued guest "
            "of The Grand Meridian Hotel. Let them know their responses will be shared with the "
            "hotel leadership team. If they expressed any dissatisfaction, acknowledge it with "
            "genuine empathy and assure them the team will act on it. Close by wishing them well "
            "and expressing hope to welcome them back in the future."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound post-stay survey call — The Grand Meridian Hotel"
    )
    parser.add_argument("phone", help="Guest phone number to call")
    parser.add_argument("--name", required=True, help="Full name of the guest")
    parser.add_argument("--reservation-number", required=True, help="Reservation reference number")
    parser.add_argument("--checkout-date", required=True, help="Date the guest checked out")
    args = parser.parse_args()

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "name": args.name,
            "reservation_number": args.reservation_number,
            "checkout_date": args.checkout_date,
        },
    )
