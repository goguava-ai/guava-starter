import guava
import os
import logging
import json
import argparse
from datetime import datetime

logging.basicConfig(level=logging.INFO)


class RecallNotificationController(guava.CallController):
    def __init__(self, contact_name, product_name, recall_reason, order_number):
        super().__init__()
        self.contact_name = contact_name
        self.product_name = product_name
        self.recall_reason = recall_reason
        self.order_number = order_number
        self.set_persona(
            organization_name="ShopNow - Customer Safety Team",
            agent_name="Casey",
            agent_purpose=(
                "to notify affected customers of an urgent product recall, "
                "provide safety instructions, and arrange a return, replacement, or store credit"
            ),
        )
        self.reach_person(
            contact_full_name=self.contact_name,
            on_success=self.begin_recall_notification,
            on_failure=self.recipient_unavailable,
        )

    def begin_recall_notification(self):
        self.set_task(
            objective=(
                f"Urgently notify {self.contact_name} that their ShopNow order #{self.order_number} "
                f"containing '{self.product_name}' is subject to a product recall due to: {self.recall_reason}. "
                "Clearly communicate the safety concern, instruct them to stop using the product immediately, "
                "confirm they have understood the recall, determine whether they still have the product in use, "
                "collect their chosen resolution (return for refund, replacement, or store credit), "
                "and confirm how they would like to receive their prepaid return label. "
                "Allow the customer to ask any questions about the recall. "
                "Maintain a calm, professional, and safety-first tone throughout."
            ),
            checklist=[
                guava.Say(
                    f"Hello {self.contact_name}, this is Casey calling from the ShopNow Customer Safety Team. "
                    "I'm reaching out regarding an important safety notice that affects a product "
                    f"from your recent order #{self.order_number}. "
                    f"We have issued an official recall for '{self.product_name}' "
                    f"due to the following safety concern: {self.recall_reason}. "
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
            on_complete=self.save_results,
        )

    def save_results(self):
        results = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "contact_name": self.contact_name,
            "product_name": self.product_name,
            "recall_reason": self.recall_reason,
            "order_number": self.order_number,
            "recall_acknowledged": self.get_field("recall_acknowledged"),
            "product_still_in_use": self.get_field("product_still_in_use"),
            "resolution_choice": self.get_field("resolution_choice"),
            "return_label_delivery_preference": self.get_field("return_label_delivery_preference"),
            "questions_about_recall": self.get_field("questions_about_recall"),
        }
        print(json.dumps(results, indent=2))
        logging.info(
            "Recall notification call completed for %s, order %s, product '%s'",
            self.contact_name,
            self.order_number,
            self.product_name,
        )
        self.hangup(
            final_instructions=(
                "Thank the customer for their time and for taking this matter seriously. "
                "Confirm that their chosen resolution and return label delivery preference have been recorded "
                "and that they will be contacted within 24 to 48 hours with next steps. "
                "Provide the ShopNow Customer Safety Team phone number or support email if they have "
                "further questions. Emphasize that their safety is ShopNow's highest priority, "
                "and close the call with care and professionalism."
            )
        )

    def recipient_unavailable(self):
        logging.warning(
            "Could not reach %s for recall notification on order %s, product '%s'.",
            self.contact_name,
            self.order_number,
            self.product_name,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ShopNow product recall notification agent")
    parser.add_argument("phone", help="Customer phone number to call")
    parser.add_argument("--name", required=True, help="Customer full name")
    parser.add_argument("--product-name", required=True, help="Name of the recalled product")
    parser.add_argument(
        "--recall-reason", required=True, help="Reason or description of the safety issue triggering the recall"
    )
    parser.add_argument("--order-number", required=True, help="Customer's order number containing the product")
    args = parser.parse_args()

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=RecallNotificationController(
            contact_name=args.name,
            product_name=args.product_name,
            recall_reason=args.recall_reason,
            order_number=args.order_number,
        ),
    )
