import guava
import os
import logging
import json
import argparse
import requests
from datetime import datetime

logging.basicConfig(level=logging.INFO)

STORE_HASH = os.environ["BIGCOMMERCE_STORE_HASH"]
AUTH_TOKEN = os.environ["BIGCOMMERCE_AUTH_TOKEN"]
V3_BASE = f"https://api.bigcommerce.com/stores/{STORE_HASH}/v3"

HEADERS = {
    "X-Auth-Token": AUTH_TOKEN,
    "Content-Type": "application/json",
    "Accept": "application/json",
}


class AbandonedCartRecoveryController(guava.CallController):
    def __init__(
        self,
        customer_name: str,
        customer_email: str,
        cart_id: str,
        cart_total: str,
    ):
        super().__init__()
        self.customer_name = customer_name
        self.customer_email = customer_email
        self.cart_id = cart_id
        self.cart_total = cart_total
        self.line_items_summary = ""

        # Attempt to fetch cart line items so the agent can mention specific products
        try:
            resp = requests.get(
                f"{V3_BASE}/abandoned-carts/{cart_id}",
                headers=HEADERS,
                timeout=10,
            )
            resp.raise_for_status()
            cart_data = resp.json()
            line_items = (
                cart_data.get("data", {}).get("cart", {}).get("line_items", {})
                or cart_data.get("data", {}).get("line_items", {})
                or {}
            )
            physical = line_items.get("physical_items", [])
            digital = line_items.get("digital_items", [])
            all_items = physical + digital
            if all_items:
                parts = []
                for item in all_items[:5]:
                    name = item.get("name", "item")
                    qty = item.get("quantity", 1)
                    parts.append(f"{qty}x {name}")
                self.line_items_summary = ", ".join(parts)
                logging.info("Cart line items fetched: %s", self.line_items_summary)
        except Exception as e:
            logging.warning("Could not fetch cart details for cart %s: %s", cart_id, e)

        self.set_persona(
            organization_name="Harbor House",
            agent_name="Riley",
            agent_purpose="to reconnect with Harbor House customers who left items in their cart and help them complete their purchase",
        )

        self.reach_person(
            contact_full_name=customer_name,
            on_success=self.begin_recovery,
            on_failure=self.leave_voicemail,
        )

    def begin_recovery(self):
        items_mention = (
            f" — including {self.line_items_summary} —"
            if self.line_items_summary
            else ""
        )

        self.set_task(
            objective=(
                f"You've reached {self.customer_name}, a Harbor House customer who left "
                f"{self.cart_total} worth of items{items_mention} in their cart. "
                "Greet them warmly, mention the cart, and find out how you can help them "
                "complete the purchase or address any concerns."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.customer_name}, this is Riley calling from Harbor House. "
                    f"I'm reaching out because it looks like you left some great items{items_mention} "
                    f"worth {self.cart_total} in your cart. I just wanted to check in and see if "
                    "there's anything I can help you with to complete your order."
                ),
                guava.Field(
                    key="customer_response",
                    description=(
                        "Find out how you can help the customer. Ask what brought them to abandon "
                        "the cart. Offer these options and capture their choice: "
                        "'yes, I'd like to complete it', 'had questions about an item', "
                        "'changed my mind', 'had a payment issue'."
                    ),
                    field_type="multiple_choice",
                    choices=[
                        "yes, I'd like to complete it",
                        "had questions about an item",
                        "changed my mind",
                        "had a payment issue",
                    ],
                    required=True,
                ),
            ],
            on_complete=self.handle_response,
        )

    def handle_response(self):
        response = self.get_field("customer_response")
        label = (response or "").strip().lower()

        if "complete it" in label:
            self._handle_wants_to_complete()
        elif "questions" in label:
            self._handle_product_questions()
        elif "changed" in label:
            self._handle_changed_mind()
        elif "payment" in label:
            self._handle_payment_issue()
        else:
            self.hangup(
                final_instructions=(
                    "Thank the customer for their time and let them know their cart is saved "
                    "at harborhouse.com whenever they're ready. Wish them a great day."
                )
            )

    def _handle_wants_to_complete(self):
        self.hangup(
            final_instructions=(
                f"Let {self.customer_name} know that their cart is saved and ready for them. "
                "Offer to transfer them to the Harbor House sales team so they can complete "
                "the order by phone, or let them know they can finish checkout by visiting "
                "harborhouse.com — their cart will still be there. "
                "Thank them for shopping with Harbor House and wish them a great day."
            )
        )

    def _handle_product_questions(self):
        self.set_task(
            objective=(
                f"{self.customer_name} has questions about one of the items in their cart. "
                "Find out what they'd like to know and answer if possible, or arrange to connect "
                "them with a product specialist."
            ),
            checklist=[
                guava.Field(
                    key="question_about",
                    description=(
                        "Ask the customer what their question is about — which product and "
                        "what specifically they'd like to know (size, material, compatibility, etc.). "
                        "Capture their question in full."
                    ),
                    field_type="text",
                    required=True,
                ),
            ],
            on_complete=self._finalize_questions,
        )

    def _finalize_questions(self):
        question = self.get_field("question_about")
        print(json.dumps({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "customer_name": self.customer_name,
            "customer_email": self.customer_email,
            "cart_id": self.cart_id,
            "outcome": "product_question",
            "question": question,
        }, indent=2))
        logging.info("Cart recovery — product question logged for %s.", self.customer_name)
        self.hangup(
            final_instructions=(
                f"Address {self.customer_name}'s question about '{question}' based on product details. "
                "If unable to fully address the question, transfer them to a Harbor House "
                "product specialist who can provide complete details. "
                "Thank them for calling and let them know their cart is saved."
            )
        )

    def _handle_changed_mind(self):
        self.set_task(
            objective=(
                f"{self.customer_name} has changed their mind about the purchase. "
                "Understand why and — if price was the issue — offer a discount code."
            ),
            checklist=[
                guava.Field(
                    key="changed_mind_reason",
                    description=(
                        "Ask why they decided not to complete the order. "
                        "Offer these options: 'too expensive', 'found it elsewhere', "
                        "'don't need it anymore'."
                    ),
                    field_type="multiple_choice",
                    choices=["too expensive", "found it elsewhere", "don't need it anymore"],
                    required=True,
                ),
            ],
            on_complete=self._finalize_changed_mind,
        )

    def _finalize_changed_mind(self):
        reason = self.get_field("changed_mind_reason")
        print(json.dumps({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "customer_name": self.customer_name,
            "customer_email": self.customer_email,
            "cart_id": self.cart_id,
            "outcome": "changed_mind",
            "reason": reason,
        }, indent=2))
        logging.info("Cart recovery — customer changed mind, reason: %s.", reason)

        reason_lower = (reason or "").lower()
        if "expensive" in reason_lower or "price" in reason_lower:
            self.hangup(
                final_instructions=(
                    f"Empathize with {self.customer_name} about the price. "
                    "Let them know you'd like to offer them a discount on their order — "
                    "share the code SAVE10 which gives them 10% off their cart. "
                    "Let them know the code can be entered at checkout on harborhouse.com "
                    "and that their cart is still saved. "
                    "Thank them warmly for giving Harbor House another chance."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Thank {self.customer_name} for their time and for letting you know. "
                    "Let them know that Harbor House always has new arrivals and that they're "
                    "welcome to visit harborhouse.com any time. Wish them a great day."
                )
            )

    def _handle_payment_issue(self):
        self.hangup(
            final_instructions=(
                f"Apologize to {self.customer_name} for the trouble and let them know you can "
                "help them complete the order over the phone right now if they'd like — offer "
                "to transfer them to the Harbor House sales team to process payment securely. "
                "Alternatively, direct them to harborhouse.com/help/payments for guidance on "
                "supported payment methods and troubleshooting steps. "
                "Let them know their cart is saved so no items will be lost. "
                "Thank them for their patience."
            )
        )

    def leave_voicemail(self):
        logging.info(
            "Could not reach %s for cart recovery. Leaving voicemail.",
            self.customer_name,
        )
        self.hangup(
            final_instructions=(
                f"Leave a brief, friendly voicemail for {self.customer_name}. "
                "Introduce yourself as Riley from Harbor House. Let them know they left some "
                f"great items worth {self.cart_total} in their cart and that it's still saved "
                "for them at harborhouse.com whenever they're ready. "
                "Let them know they can call back with any questions. Keep it short and upbeat."
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Harbor House abandoned cart recovery agent"
    )
    parser.add_argument("phone", help="Customer phone number to call (E.164 format)")
    parser.add_argument("--name", required=True, help="Customer full name")
    parser.add_argument("--email", required=True, help="Customer email address")
    parser.add_argument("--cart-id", required=True, help="BigCommerce abandoned cart token/ID")
    parser.add_argument(
        "--cart-total",
        required=True,
        help="Human-readable cart total, e.g. '$89.99'",
    )
    args = parser.parse_args()

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=AbandonedCartRecoveryController(
            customer_name=args.name,
            customer_email=args.email,
            cart_id=args.cart_id,
            cart_total=args.cart_total,
        ),
    )
