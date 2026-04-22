import guava
import os
import logging
import json
import argparse
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)


class PostPurchaseSurveyController(guava.CallController):
    def __init__(self, contact_name, product_name, order_number):
        super().__init__()
        self.contact_name = contact_name
        self.product_name = product_name
        self.order_number = order_number
        self.set_persona(
            organization_name="ShopNow",
            agent_name="Jamie",
            agent_purpose=(
                "to collect structured feedback about a customer's recent purchase experience, "
                "including product satisfaction and delivery quality"
            ),
        )
        self.reach_person(
            contact_full_name=self.contact_name,
            on_success=self.begin_survey,
            on_failure=self.recipient_unavailable,
        )

    def begin_survey(self):
        self.set_task(
            objective=(
                f"Conduct a brief post-purchase satisfaction survey with {self.contact_name} "
                f"regarding their recent ShopNow order #{self.order_number} for '{self.product_name}'. "
                "Collect a numeric product rating from 1 to 5, a delivery experience rating from 1 to 5, "
                "confirm whether the product matched its description, ask if they would purchase again, "
                "obtain permission to use their feedback as a review, "
                "and optionally gather suggestions for improvement. "
                "Keep the tone friendly, brief, and appreciative of their time."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.contact_name}, this is Jamie from ShopNow. "
                    f"I'm calling because you recently received your order of '{self.product_name}', "
                    f"order number {self.order_number}. "
                    "We'd love just two minutes of your time to hear how everything went. "
                    "Your feedback helps us serve you better."
                ),
                guava.Say(
                    "First, on a scale of 1 to 5 — where 1 is very dissatisfied and 5 is extremely satisfied — "
                    "how would you rate the product itself?"
                ),
                guava.Field(
                    key="product_rating",
                    description="Customer's overall product satisfaction rating on a scale of 1 to 5",
                    field_type="integer",
                    required=True,
                ),
                guava.Say(
                    "Great. Now using the same 1 to 5 scale, how would you rate your delivery experience — "
                    "including packaging, timeliness, and condition of the item when it arrived?"
                ),
                guava.Field(
                    key="delivery_experience_rating",
                    description="Customer's delivery experience rating on a scale of 1 to 5",
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="product_as_described",
                    description=(
                        "Whether the product matched its online description: "
                        "'yes' if fully accurate, 'no' if it did not match, "
                        "or 'partially' if only some aspects matched"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="would_purchase_again",
                    description="Whether the customer would purchase from ShopNow again, in their own words",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="review_permission",
                    description=(
                        "Whether the customer gives ShopNow permission to use their feedback as a public review "
                        "on the product page"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="improvement_feedback",
                    description=(
                        "Any suggestions the customer has for how ShopNow could improve the product or experience. "
                        "Leave blank if they have no additional feedback."
                    ),
                    field_type="text",
                    required=False,
                ),
            ],
            on_complete=self.save_results,
        )

    def save_results(self):
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "contact_name": self.contact_name,
            "product_name": self.product_name,
            "order_number": self.order_number,
            "product_rating": self.get_field("product_rating"),
            "delivery_experience_rating": self.get_field("delivery_experience_rating"),
            "product_as_described": self.get_field("product_as_described"),
            "would_purchase_again": self.get_field("would_purchase_again"),
            "review_permission": self.get_field("review_permission"),
            "improvement_feedback": self.get_field("improvement_feedback"),
        }
        print(json.dumps(results, indent=2))
        logging.info(
            "Post-purchase survey completed for %s, order %s", self.contact_name, self.order_number
        )
        self.hangup(
            final_instructions=(
                "Thank the customer sincerely for taking the time to share their feedback. "
                "Let them know their responses will be used to improve the ShopNow experience. "
                "Remind them they can reach ShopNow support anytime with questions, "
                "and wish them a wonderful day before ending the call."
            )
        )

    def recipient_unavailable(self):
        logging.warning(
            "Could not reach %s for post-purchase survey on order %s.",
            self.contact_name,
            self.order_number,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ShopNow post-purchase survey agent")
    parser.add_argument("phone", help="Customer phone number to call")
    parser.add_argument("--name", required=True, help="Customer full name")
    parser.add_argument("--product-name", required=True, help="Name of the purchased product")
    parser.add_argument("--order-number", required=True, help="Order number")
    args = parser.parse_args()

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=PostPurchaseSurveyController(
            contact_name=args.name,
            product_name=args.product_name,
            order_number=args.order_number,
        ),
    )
