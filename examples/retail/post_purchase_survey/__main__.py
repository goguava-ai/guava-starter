import guava
import os
import logging
from guava import logging_utils
import json
import argparse
from datetime import datetime, timezone


agent = guava.Agent(
    name="Jamie",
    organization="ShopNow",
    purpose=(
        "to collect structured feedback about a customer's recent purchase experience, "
        "including product satisfaction and delivery quality"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(contact_full_name=call.get_variable("contact_name"))


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    contact_name = call.get_variable("contact_name")
    product_name = call.get_variable("product_name")
    order_number = call.get_variable("order_number")

    if outcome == "unavailable":
        logging.warning(
            "Could not reach %s for post-purchase survey on order %s.",
            contact_name,
            order_number,
        )
    elif outcome == "available":
        call.set_task(
            "post_purchase_survey",
            objective=(
                f"Conduct a brief post-purchase satisfaction survey with {contact_name} "
                f"regarding their recent ShopNow order #{order_number} for '{product_name}'. "
                "Collect a numeric product rating from 1 to 5, a delivery experience rating from 1 to 5, "
                "confirm whether the product matched its description, ask if they would purchase again, "
                "obtain permission to use their feedback as a review, "
                "and optionally gather suggestions for improvement. "
                "Keep the tone friendly, brief, and appreciative of their time."
            ),
            checklist=[
                guava.Say(
                    f"Hi {contact_name}, this is Jamie from ShopNow. "
                    f"I'm calling because you recently received your order of '{product_name}', "
                    f"order number {order_number}. "
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
        )


@agent.on_task_complete("post_purchase_survey")
def on_done(call: guava.Call) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "contact_name": call.get_variable("contact_name"),
        "product_name": call.get_variable("product_name"),
        "order_number": call.get_variable("order_number"),
        "product_rating": call.get_field("product_rating"),
        "delivery_experience_rating": call.get_field("delivery_experience_rating"),
        "product_as_described": call.get_field("product_as_described"),
        "would_purchase_again": call.get_field("would_purchase_again"),
        "review_permission": call.get_field("review_permission"),
        "improvement_feedback": call.get_field("improvement_feedback"),
    }
    print(json.dumps(results, indent=2))
    logging.info(
        "Post-purchase survey completed for %s, order %s",
        call.get_variable("contact_name"),
        call.get_variable("order_number"),
    )
    call.hangup(
        final_instructions=(
            "Thank the customer sincerely for taking the time to share their feedback. "
            "Let them know their responses will be used to improve the ShopNow experience. "
            "Remind them they can reach ShopNow support anytime with questions, "
            "and wish them a wonderful day before ending the call."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(description="ShopNow post-purchase survey agent")
    parser.add_argument("phone", help="Customer phone number to call")
    parser.add_argument("--name", required=True, help="Customer full name")
    parser.add_argument("--product-name", required=True, help="Name of the purchased product")
    parser.add_argument("--order-number", required=True, help="Order number")
    args = parser.parse_args()

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "contact_name": args.name,
            "product_name": args.product_name,
            "order_number": args.order_number,
        },
    )
