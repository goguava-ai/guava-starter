import guava
import os
import logging
import argparse
import pymysql
import pymysql.cursors

logging.basicConfig(level=logging.INFO)


def get_connection():
    return pymysql.connect(
        host=os.environ["MYSQL_HOST"],
        port=int(os.environ.get("MYSQL_PORT", "3306")),
        user=os.environ["MYSQL_USER"],
        password=os.environ["MYSQL_PASSWORD"],
        database=os.environ["MYSQL_DATABASE"],
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


def get_cart(cart_id: int) -> dict | None:
    """Returns the cart row for the given cart_id."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, customer_name, customer_email,
                       total_amount, currency, created_at
                FROM carts
                WHERE id = %s
                LIMIT 1
                """,
                (cart_id,),
            )
            return cursor.fetchone()


def get_cart_items(cart_id: int) -> list[dict]:
    """Returns the line items in the cart."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT product_name, quantity, unit_price
                FROM cart_items
                WHERE cart_id = %s
                """,
                (cart_id,),
            )
            return cursor.fetchall()


def mark_cart_contacted(cart_id: int, outcome: str) -> None:
    """Records the recovery call outcome on the cart row."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE carts
                SET recovery_outcome = %s, contacted_at = NOW()
                WHERE id = %s
                """,
                (outcome, cart_id),
            )


class CartRecoveryController(guava.CallController):
    def __init__(self, cart_id: int, customer_name: str):
        super().__init__()
        self.cart_id = cart_id
        self.customer_name = customer_name
        self.total_str = ""
        self.item_summary = ""

        try:
            cart = get_cart(cart_id)
            if cart:
                total = cart.get("total_amount")
                currency = (cart.get("currency") or "USD").upper()
                self.total_str = f"${float(total):,.2f} {currency}" if total else ""
            items = get_cart_items(cart_id)
            if items:
                lines = [f"{r['product_name']} ×{r['quantity']}" for r in items]
                self.item_summary = ", ".join(lines)
        except Exception as e:
            logging.error("Failed to fetch cart %d: %s", cart_id, e)

        self.set_persona(
            organization_name="Peak Outdoors",
            agent_name="Riley",
            agent_purpose=(
                "to follow up with Peak Outdoors customers who left items in their cart "
                "and help them complete their purchase"
            ),
        )

        self.reach_person(
            contact_full_name=self.customer_name,
            on_success=self.deliver_followup,
            on_failure=self.recipient_unavailable,
        )

    def deliver_followup(self):
        cart_note = f" You had {self.item_summary} in your cart." if self.item_summary else ""
        total_note = f" The total comes to {self.total_str}." if self.total_str else ""

        self.set_task(
            objective=(
                f"Follow up with {self.customer_name} about items left in their Peak Outdoors cart. "
                + (f"Cart contents: {self.item_summary}." if self.item_summary else "")
                + (f" Cart total: {self.total_str}." if self.total_str else "")
                + " Find out if they have questions and help them complete the purchase."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.customer_name}, this is Riley from Peak Outdoors. "
                    "I noticed you left some items in your cart and wanted to reach out "
                    "in case you had any questions or needed help completing your order."
                    + cart_note
                    + total_note
                ),
                guava.Field(
                    key="reason_for_leaving",
                    field_type="multiple_choice",
                    description="Ask if there was a specific reason they didn't complete the purchase.",
                    choices=[
                        "had questions about the product",
                        "price concern",
                        "wasn't ready to buy yet",
                        "technical issue at checkout",
                        "just browsing",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="purchase_intent",
                    field_type="multiple_choice",
                    description="Ask if they're still interested in the items.",
                    choices=[
                        "yes, I'd like to complete the order",
                        "maybe, I have a question first",
                        "no, I've decided not to purchase",
                    ],
                    required=True,
                ),
            ],
            on_complete=self.handle_response,
        )

    def handle_response(self):
        reason = self.get_field("reason_for_leaving") or "unknown"
        intent = self.get_field("purchase_intent") or "no"

        logging.info(
            "Cart recovery for cart %d — reason: %s, intent: %s",
            self.cart_id, reason, intent,
        )

        if "complete" in intent:
            outcome = "converted"
        elif "question" in intent:
            outcome = "interested"
        else:
            outcome = "declined"

        try:
            mark_cart_contacted(self.cart_id, outcome)
        except Exception as e:
            logging.error("Failed to update cart %d outcome: %s", self.cart_id, e)

        if "complete" in intent:
            self.hangup(
                final_instructions=(
                    f"Let {self.customer_name} know you'll send a direct checkout link "
                    "to the email on file so they can finish the purchase in one click. "
                    "Thank them for choosing Peak Outdoors."
                )
            )
        elif "question" in intent:
            self.hangup(
                final_instructions=(
                    f"Answer any product questions {self.customer_name} has to the best of your ability. "
                    "For detailed technical questions, offer to have a gear specialist call them back. "
                    "Let them know their cart will be saved for 7 days."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Thank {self.customer_name} for their time. "
                    "Let them know their cart will be saved if they change their mind, "
                    "and invite them to visit peakoutdoors.com or call back anytime. "
                    "Wish them a great day."
                )
            )

    def recipient_unavailable(self):
        logging.info(
            "Unable to reach %s for cart recovery on cart %d", self.customer_name, self.cart_id
        )
        try:
            mark_cart_contacted(self.cart_id, "voicemail")
        except Exception as e:
            logging.error("Failed to update cart %d outcome: %s", self.cart_id, e)
        self.hangup(
            final_instructions=(
                f"Leave a brief, friendly voicemail for {self.customer_name} from Peak Outdoors. "
                "Let them know you noticed items in their cart and you're here to help "
                "if they have any questions. Give the callback number 1-800-PEAK-OUT. Keep it short."
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Outbound cart recovery call for a Peak Outdoors customer."
    )
    parser.add_argument("phone", help="Customer's phone number (E.164, e.g. +15551234567)")
    parser.add_argument("--cart-id", required=True, type=int, help="Cart ID in the database")
    parser.add_argument("--name", required=True, help="Customer's full name")
    args = parser.parse_args()

    logging.info(
        "Initiating cart recovery call to %s (%s) for cart %d",
        args.name, args.phone, args.cart_id,
    )

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=CartRecoveryController(
            cart_id=args.cart_id,
            customer_name=args.name,
        ),
    )
