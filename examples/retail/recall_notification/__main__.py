import argparse
import json
import logging
import os
from datetime import datetime, timezone

import guava
from guava import logging_utils

agent = guava.Agent(
    name="Casey",
    organization="ShopNow - Customer Safety Team",
    purpose=(
        "to notify affected customers of an urgent product recall, "
        "provide safety instructions, and arrange a return, replacement, or store credit"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(contact_full_name=call.get_variable("contact_name"))


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    contact_name = call.get_variable("contact_name")
    product_name = call.get_variable("product_name")
    recall_reason = call.get_variable("recall_reason")
    order_number = call.get_variable("order_number")

    if outcome == "unavailable":
        logging.warning(
            "Could not reach %s for recall notification on order %s, product '%s'.",
            contact_name,
            order_number,
            product_name,
        )
    elif outcome == "available":
        call.set_task(
            "recall_notification",
            objective=(
                f"Urgently notify {contact_name} that their ShopNow order #{order_number} "
                f"containing '{product_name}' is subject to a product recall due to: {recall_reason}. "
                "Clearly communicate the safety concern, instruct them to stop using the product immediately, "
                "confirm they have understood the recall, determine whether they still have the product in use, "
                "collect their chosen resolution (return for refund, replacement, or store credit), "
                "and confirm how they would like to receive their prepaid return label. "
                "Allow the customer to ask any questions about the recall. "
                "Maintain a calm, professional, and safety-first tone throughout."
            ),
            checklist=[
                guava.Say(
                    f"Hello {contact_name}, this is Casey calling from the ShopNow Customer Safety Team. "
                    "I'm reaching out regarding an important safety notice that affects a product "
                    f"from your recent order #{order_number}. "
                    f"We have issued an official recall for '{product_name}' "
                    f"due to the following safety concern: {recall_reason}. "
                    "Please stop using this product immediately as a precautionary measure. "
                    "We sincerely apologize for any concern this may cause and want to assure you "
                    "that your safety is our absolute top priority."
                ),
                guava.Field(
                    key="recall_acknowledged",
                    description=(
                        "Confirmation that the customer has heard and understood the recall notice "
                        "for the affected product"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="product_still_in_use",
                    description=(
                        "Whether the customer still has the recalled product and has been using it: "
                        "'yes', 'no', or details about the current status of the product"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Say(
                    "We want to make this as easy as possible for you. "
                    "We can arrange one of three resolutions at no cost to you: "
                    "you can return the product for a full refund, receive a free replacement once "
                    "the corrected product is available, or receive store credit to use on any future purchase."
                ),
                guava.Field(
                    key="resolution_choice",
                    description=(
                        "The customer's preferred resolution for the recalled product: "
                        "'return_refund' for a full refund, "
                        "'replacement' for a free replacement unit, "
                        "or 'store_credit' for store credit"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="return_label_delivery_preference",
                    description=(
                        "How the customer would like to receive their prepaid return shipping label: "
                        "'email' to receive it by email, or 'mail' to receive a physical label by post"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="questions_about_recall",
                    description=(
                        "Any questions or concerns the customer raised about the recall, the safety issue, "
                        "the return process, or the resolution options. "
                        "Leave blank if they had no further questions."
                    ),
                    field_type="text",
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("recall_notification")
def on_done(call: guava.Call) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "contact_name": call.get_variable("contact_name"),
        "product_name": call.get_variable("product_name"),
        "recall_reason": call.get_variable("recall_reason"),
        "order_number": call.get_variable("order_number"),
        "recall_acknowledged": call.get_field("recall_acknowledged"),
        "product_still_in_use": call.get_field("product_still_in_use"),
        "resolution_choice": call.get_field("resolution_choice"),
        "return_label_delivery_preference": call.get_field("return_label_delivery_preference"),
        "questions_about_recall": call.get_field("questions_about_recall"),
    }
    print(json.dumps(results, indent=2))
    logging.info(
        "Recall notification call completed for %s, order %s, product '%s'",
        call.get_variable("contact_name"),
        call.get_variable("order_number"),
        call.get_variable("product_name"),
    )
    call.hangup(
        final_instructions=(
            "Thank the customer for their time and for taking this matter seriously. "
            "Confirm that their chosen resolution and return label delivery preference have been recorded "
            "and that they will be contacted within 24 to 48 hours with next steps. "
            "Provide the ShopNow Customer Safety Team phone number or support email if they have "
            "further questions. Emphasize that their safety is ShopNow's highest priority, "
            "and close the call with care and professionalism."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(description="ShopNow product recall notification agent")
    parser.add_argument("phone", help="Customer phone number to call")
    parser.add_argument("--name", required=True, help="Customer full name")
    parser.add_argument("--product-name", required=True, help="Name of the recalled product")
    parser.add_argument(
        "--recall-reason", required=True, help="Reason or description of the safety issue triggering the recall"
    )
    parser.add_argument("--order-number", required=True, help="Customer's order number containing the product")
    args = parser.parse_args()

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "contact_name": args.name,
            "product_name": args.product_name,
            "recall_reason": args.recall_reason,
            "order_number": args.order_number,
        },
    )
