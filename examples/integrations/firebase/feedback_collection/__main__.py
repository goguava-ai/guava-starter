import argparse
import logging
import os

import firebase_admin
import guava
from firebase_admin import credentials, firestore
from guava import logging_utils

cred = credentials.Certificate(os.environ["GOOGLE_APPLICATION_CREDENTIALS"])
firebase_admin.initialize_app(cred)
db = firestore.client()

FEEDBACK_COLLECTION = os.environ.get("FIRESTORE_FEEDBACK_COLLECTION", "feedback")


def write_feedback(data: dict) -> str:
    """Write feedback document to Firestore and return the document ID."""
    data["collected_at"] = firestore.SERVER_TIMESTAMP
    data["source"] = "voice"
    _, doc_ref = db.collection(FEEDBACK_COLLECTION).add(data)
    return doc_ref.id


agent = guava.Agent(
    name="Riley",
    organization="Crestline Services",
    purpose=(
        "to collect post-service feedback from Crestline customers and "
        "ensure their experience was excellent"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    service_date = call.get_variable("service_date")
    service_type = call.get_variable("service_type")

    call.set_task(
        "collect_feedback",
        objective=(
            f"Collect feedback from {customer_name} about their recent "
            f"{service_type} on {service_date}."
        ),
        checklist=[
            guava.Say(
                f"Hi {customer_name}, this is Riley calling from Crestline Services. "
                f"I'm following up on your recent {service_type} on {service_date}. "
                "I'd love to get two minutes of your feedback — it really helps us improve. "
                "Is now a good time?"
            ),
            guava.Field(
                key="overall_rating",
                field_type="multiple_choice",
                description=(
                    "Ask them to rate their overall experience on a scale of 1 to 5, "
                    "where 5 is excellent."
                ),
                choices=["1 — very poor", "2 — poor", "3 — okay", "4 — good", "5 — excellent"],
                required=True,
            ),
            guava.Field(
                key="what_went_well",
                field_type="text",
                description=(
                    "Ask what they felt went well during the service. "
                    "Let them share freely."
                ),
                required=False,
            ),
            guava.Field(
                key="what_could_improve",
                field_type="text",
                description=(
                    "Ask if there's anything they felt could have been better. "
                    "Be empathetic and genuinely curious, not defensive."
                ),
                required=False,
            ),
            guava.Field(
                key="would_recommend",
                field_type="multiple_choice",
                description=(
                    "Ask how likely they are to recommend Crestline to a friend or colleague."
                ),
                choices=[
                    "very likely",
                    "likely",
                    "neutral",
                    "unlikely",
                    "very unlikely",
                ],
                required=True,
            ),
            guava.Field(
                key="additional_comments",
                field_type="text",
                description=(
                    "Ask if there's anything else they'd like to share or any questions "
                    "we can answer for them."
                ),
                required=False,
            ),
        ],
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    if outcome == "unavailable":
        customer_name = call.get_variable("customer_name")
        service_type = call.get_variable("service_type")
        logging.info("Unable to reach %s for feedback survey", customer_name)
        call.hangup(
            final_instructions=(
                f"Leave a brief, friendly voicemail for {customer_name} from Crestline Services. "
                f"Let them know you were calling to follow up on their recent {service_type} "
                "and gather feedback. Let them know there's nothing urgent — a quick survey is "
                "also available via the link in their service completion email. Keep it short."
            )
        )
    elif outcome == "available":
        customer_name = call.get_variable("customer_name")
        service_date = call.get_variable("service_date")
        service_type = call.get_variable("service_type")
        call.set_task(
            "collect_feedback",
            objective=(
                f"Collect feedback from {customer_name} about their recent "
                f"{service_type} on {service_date}."
            ),
            checklist=[
                guava.Say(
                    f"Hi {customer_name}, this is Riley calling from Crestline Services. "
                    f"I'm following up on your recent {service_type} on {service_date}. "
                    "I'd love to get two minutes of your feedback — it really helps us improve. "
                    "Is now a good time?"
                ),
                guava.Field(
                    key="overall_rating",
                    field_type="multiple_choice",
                    description=(
                        "Ask them to rate their overall experience on a scale of 1 to 5, "
                        "where 5 is excellent."
                    ),
                    choices=["1 — very poor", "2 — poor", "3 — okay", "4 — good", "5 — excellent"],
                    required=True,
                ),
                guava.Field(
                    key="what_went_well",
                    field_type="text",
                    description=(
                        "Ask what they felt went well during the service. "
                        "Let them share freely."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="what_could_improve",
                    field_type="text",
                    description=(
                        "Ask if there's anything they felt could have been better. "
                        "Be empathetic and genuinely curious, not defensive."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="would_recommend",
                    field_type="multiple_choice",
                    description=(
                        "Ask how likely they are to recommend Crestline to a friend or colleague."
                    ),
                    choices=[
                        "very likely",
                        "likely",
                        "neutral",
                        "unlikely",
                        "very unlikely",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="additional_comments",
                    field_type="text",
                    description=(
                        "Ask if there's anything else they'd like to share or any questions "
                        "we can answer for them."
                    ),
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("collect_feedback")
def on_done(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    customer_id = call.get_variable("customer_id")

    rating_str = call.get_field("overall_rating") or "3 — okay"
    rating_num = int(rating_str[0]) if rating_str else 3
    went_well = call.get_field("what_went_well") or ""
    could_improve = call.get_field("what_could_improve") or ""
    recommend = call.get_field("would_recommend") or "neutral"
    comments = call.get_field("additional_comments") or ""

    logging.info(
        "Feedback from %s (customer_id: %s) — rating: %s/5, recommend: %s",
        customer_name, customer_id, rating_num, recommend,
    )

    feedback_data = {
        "customer_name": customer_name,
        "customer_id": customer_id,
        "service_date": call.get_variable("service_date"),
        "service_type": call.get_variable("service_type"),
        "overall_rating": rating_num,
        "what_went_well": went_well,
        "what_could_improve": could_improve,
        "would_recommend": recommend,
        "additional_comments": comments,
        "requires_followup": rating_num <= 2 or recommend in ("unlikely", "very unlikely"),
    }

    try:
        doc_id = write_feedback(feedback_data)
        logging.info("Feedback written to Firestore: %s", doc_id)
    except Exception as e:
        logging.error("Failed to write feedback for %s: %s", customer_id, e)

    if rating_num <= 2:
        call.hangup(
            final_instructions=(
                f"Thank {customer_name} sincerely for their honest feedback. "
                "Let them know their concerns have been noted and a manager will "
                "personally follow up with them within one business day. "
                "Apologize genuinely for any shortcomings and assure them we take "
                "this seriously. Wish them a good day."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {customer_name} warmly for taking the time to share their feedback. "
                "If they said anything particularly positive, acknowledge it with genuine appreciation. "
                "Let them know their feedback helps the team get better every day. "
                "Wish them well and thank them for choosing Crestline Services."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound post-service feedback collection call."
    )
    parser.add_argument("phone", help="Customer phone number (E.164, e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Customer full name")
    parser.add_argument("--customer-id", required=True, help="Customer ID in Firestore")
    parser.add_argument("--service-date", required=True, help="Date of service (e.g. 'March 28')")
    parser.add_argument("--service-type", default="service visit", help="Type of service performed")
    args = parser.parse_args()

    logging.info("Calling %s (%s) for post-service feedback", args.name, args.phone)

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "customer_name": args.name,
            "customer_id": args.customer_id,
            "service_date": args.service_date,
            "service_type": args.service_type,
        },
    )
