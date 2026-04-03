import guava
import os
import logging
import argparse
import firebase_admin
from firebase_admin import credentials, firestore

logging.basicConfig(level=logging.INFO)

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


class FeedbackCollectionController(guava.CallController):
    def __init__(
        self,
        customer_name: str,
        customer_id: str,
        service_date: str,
        service_type: str,
    ):
        super().__init__()
        self.customer_name = customer_name
        self.customer_id = customer_id
        self.service_date = service_date
        self.service_type = service_type

        self.set_persona(
            organization_name="Crestline Services",
            agent_name="Riley",
            agent_purpose=(
                "to collect post-service feedback from Crestline customers and "
                "ensure their experience was excellent"
            ),
        )

        self.reach_person(
            contact_full_name=customer_name,
            on_success=self.begin_survey,
            on_failure=self.recipient_unavailable,
        )

    def begin_survey(self):
        self.set_task(
            objective=(
                f"Collect feedback from {self.customer_name} about their recent "
                f"{self.service_type} on {self.service_date}."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.customer_name}, this is Riley calling from Crestline Services. "
                    f"I'm following up on your recent {self.service_type} on {self.service_date}. "
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
            on_complete=self.save_and_close,
        )

    def save_and_close(self):
        rating_str = self.get_field("overall_rating") or "3 — okay"
        rating_num = int(rating_str[0]) if rating_str else 3
        went_well = self.get_field("what_went_well") or ""
        could_improve = self.get_field("what_could_improve") or ""
        recommend = self.get_field("would_recommend") or "neutral"
        comments = self.get_field("additional_comments") or ""

        logging.info(
            "Feedback from %s (customer_id: %s) — rating: %s/5, recommend: %s",
            self.customer_name, self.customer_id, rating_num, recommend,
        )

        feedback_data = {
            "customer_name": self.customer_name,
            "customer_id": self.customer_id,
            "service_date": self.service_date,
            "service_type": self.service_type,
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
            logging.error("Failed to write feedback for %s: %s", self.customer_id, e)

        if rating_num <= 2:
            self.hangup(
                final_instructions=(
                    f"Thank {self.customer_name} sincerely for their honest feedback. "
                    "Let them know their concerns have been noted and a manager will "
                    "personally follow up with them within one business day. "
                    "Apologize genuinely for any shortcomings and assure them we take "
                    "this seriously. Wish them a good day."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Thank {self.customer_name} warmly for taking the time to share their feedback. "
                    "If they said anything particularly positive, acknowledge it with genuine appreciation. "
                    "Let them know their feedback helps the team get better every day. "
                    "Wish them well and thank them for choosing Crestline Services."
                )
            )

    def recipient_unavailable(self):
        logging.info("Unable to reach %s for feedback survey", self.customer_name)
        self.hangup(
            final_instructions=(
                f"Leave a brief, friendly voicemail for {self.customer_name} from Crestline Services. "
                f"Let them know you were calling to follow up on their recent {self.service_type} "
                "and gather feedback. Let them know there's nothing urgent — a quick survey is "
                "also available via the link in their service completion email. Keep it short."
            )
        )


if __name__ == "__main__":
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

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=FeedbackCollectionController(
            customer_name=args.name,
            customer_id=args.customer_id,
            service_date=args.service_date,
            service_type=args.service_type,
        ),
    )
