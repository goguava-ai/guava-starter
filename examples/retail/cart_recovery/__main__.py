import guava
import os
import logging
from guava import logging_utils
import json
import argparse
from datetime import datetime, timezone



class CartRecoveryController(guava.CallController):
    def __init__(self, contact_name, cart_items, cart_value):
        super().__init__()
        self.contact_name = contact_name
        self.cart_items = cart_items
        self.cart_value = cart_value
        self.set_persona(
            organization_name="ShopNow",
            agent_name="Riley",
            agent_purpose=(
                "to reach out to customers who left items in their cart, "
                "answer any product questions, offer assistance or an incentive, "
                "and help them complete their purchase"
            ),
        )
        self.reach_person(
            contact_full_name=self.contact_name,
            on_success=self.begin_cart_recovery,
            on_failure=self.recipient_unavailable,
        )

    def begin_cart_recovery(self):
        self.set_task(
            objective=(
                f"Re-engage {self.contact_name}, who left a ShopNow cart worth {self.cart_value} "
                f"containing: {self.cart_items}. "
                "Understand why they did not complete the purchase, address any product questions, "
                "offer a discount or incentive if appropriate, ask about their preferred payment method, "
                "and determine whether they are ready to complete the order now. "
                "Be helpful and low-pressure — the goal is to assist, not to push."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.contact_name}, this is Riley calling from ShopNow. "
                    f"I noticed you had some great items saved in your cart — "
                    f"including {self.cart_items} — totaling {self.cart_value}. "
                    "I just wanted to check in and see if you had any questions or if there was "
                    "anything I could help with to make your shopping experience easier."
                ),
                guava.Field(
                    key="abandonment_reason",
                    description=(
                        "The reason the customer did not complete their purchase, in their own words. "
                        "For example: price concern, found it elsewhere, wanted to think about it, "
                        "technical issue, etc. Leave blank if they decline to share."
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="product_questions",
                    description=(
                        "Any questions or concerns the customer has about the products in their cart. "
                        "Capture their questions and any answers provided. "
                        "Leave blank if they have no product questions."
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Say(
                    "As a thank-you for your time today, we'd love to offer you a special discount "
                    "to help complete your order. I can apply a discount code to your cart right now."
                ),
                guava.Field(
                    key="discount_accepted",
                    description=(
                        "Whether the customer accepted the discount or incentive offer: "
                        "'yes', 'no', or a description of their response"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="preferred_payment_method",
                    description=(
                        "The customer's preferred payment method for completing the order, "
                        "such as credit card, PayPal, buy-now-pay-later, etc. "
                        "Leave blank if they did not specify."
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="ready_to_complete_order",
                    description=(
                        "Whether the customer is ready to complete their order now, "
                        "expressed as 'yes', 'no', or a description of their intent such as "
                        "'will complete later today' or 'needs more time'"
                    ),
                    field_type="text",
                    required=True,
                ),
            ],
            on_complete=self.save_results,
        )

    def save_results(self):
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "contact_name": self.contact_name,
            "cart_items": self.cart_items,
            "cart_value": self.cart_value,
            "abandonment_reason": self.get_field("abandonment_reason"),
            "product_questions": self.get_field("product_questions"),
            "discount_accepted": self.get_field("discount_accepted"),
            "preferred_payment_method": self.get_field("preferred_payment_method"),
            "ready_to_complete_order": self.get_field("ready_to_complete_order"),
        }
        print(json.dumps(results, indent=2))
        logging.info("Cart recovery call completed for %s", self.contact_name)
        self.hangup(
            final_instructions=(
                "Thank the customer warmly for their time. "
                "If they are ready to complete the order, let them know they can finish checkout "
                "on the ShopNow website or app and that any discount code discussed has been applied. "
                "If they are not ready, let them know their cart will be saved and the ShopNow team "
                "is available to help anytime. Wish them a great day and close the call politely."
            )
        )

    def recipient_unavailable(self):
        logging.warning(
            "Could not reach %s for cart recovery outreach.", self.contact_name
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(description="ShopNow cart recovery agent")
    parser.add_argument("phone", help="Customer phone number to call")
    parser.add_argument("--name", required=True, help="Customer full name")
    parser.add_argument(
        "--cart-items", required=True, help="Description of items in the abandoned cart"
    )
    parser.add_argument("--cart-value", required=True, help="Total estimated value of the cart")
    args = parser.parse_args()

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=CartRecoveryController(
            contact_name=args.name,
            cart_items=args.cart_items,
            cart_value=args.cart_value,
        ),
    )
