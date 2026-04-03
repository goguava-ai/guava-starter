import argparse
import guava
import os
import logging
import requests

logging.basicConfig(level=logging.INFO)

STORE = os.environ["SHOPIFY_STORE"]
BASE_URL = f"https://{STORE}.myshopify.com/admin/api/2026-01"


def get_headers() -> dict:
    return {
        "X-Shopify-Access-Token": os.environ["SHOPIFY_ACCESS_TOKEN"],
        "Content-Type": "application/json",
    }


def get_checkout(checkout_token: str) -> dict | None:
    resp = requests.get(
        f"{BASE_URL}/checkouts/{checkout_token}.json",
        headers=get_headers(),
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("checkout")


def send_recovery_email(checkout_token: str) -> bool:
    """Send abandoned cart recovery email via Shopify."""
    resp = requests.post(
        f"{BASE_URL}/checkouts/{checkout_token}/send_invoice.json",
        headers=get_headers(),
        json={"checkout": {}},
        timeout=10,
    )
    return resp.status_code in (200, 201, 202)


class AbandonedCartRecoveryController(guava.CallController):
    def __init__(self, checkout_token: str, customer_name: str):
        super().__init__()

        self._checkout_token = checkout_token
        self._checkout: dict | None = None

        try:
            self._checkout = get_checkout(checkout_token)
            logging.info("Loaded checkout %s", checkout_token)
        except Exception as e:
            logging.error("Failed to load checkout: %s", e)

        checkout = self._checkout
        if checkout:
            line_items = checkout.get("line_items", [])
            item_count = sum(i.get("quantity", 1) for i in line_items)
            total = checkout.get("total_price", "0.00")
            first_item = line_items[0].get("title", "your items") if line_items else "your items"
            context = (
                f"The customer left {item_count} item(s) in their cart totaling ${total}, "
                f"including '{first_item}'."
            )
        else:
            context = "The customer left items in their cart."

        self.set_persona(
            organization_name="Kestrel Goods",
            agent_name="Casey",
            agent_purpose="to help Kestrel Goods customers complete their purchases",
        )

        self.set_task(
            objective=(
                f"You are calling {customer_name} about items they left in their Kestrel Goods cart. "
                f"{context} "
                "Find out if they need help completing their purchase and offer a recovery email if helpful."
            ),
            checklist=[
                guava.Say(
                    f"Hi, may I speak with {customer_name}? "
                    "This is Casey calling from Kestrel Goods."
                ),
                guava.Field(
                    key="still_interested",
                    field_type="multiple_choice",
                    description=(
                        "Let them know they left some items in their cart. "
                        "Ask if they're still interested in completing their purchase."
                    ),
                    choices=["yes", "no", "had a question"],
                    required=True,
                ),
                guava.Field(
                    key="question",
                    field_type="text",
                    description="If they had a question, ask what it is so you can help.",
                    required=False,
                ),
                guava.Field(
                    key="send_reminder_email",
                    field_type="multiple_choice",
                    description=(
                        "If they are interested, offer to send a link to their cart so they can complete "
                        "the purchase at their convenience. Ask if they'd like that."
                    ),
                    choices=["yes", "no"],
                    required=False,
                ),
            ],
            on_complete=self.handle_recovery,
        )

        self.reach_person(customer_name)

    def handle_recovery(self):
        still_interested = self.get_field("still_interested") or "no"
        question = self.get_field("question") or ""
        send_email = self.get_field("send_reminder_email") or "no"

        if still_interested == "no":
            self.hangup(
                final_instructions=(
                    "Thank them for their time. Let them know we're always here if they want to shop again. "
                    "Wish them a great day."
                )
            )
            return

        email_sent = False
        if send_email == "yes" and self._checkout_token:
            try:
                email_sent = send_recovery_email(self._checkout_token)
                logging.info("Recovery email sent for checkout %s: %s", self._checkout_token, email_sent)
            except Exception as e:
                logging.error("Failed to send recovery email: %s", e)

        if question:
            self.hangup(
                final_instructions=(
                    f"Address the customer's question about '{question}' based on knowledge about Kestrel Goods. "
                    + ("A recovery link has been sent to their email. " if email_sent else "")
                    + "Thank them and encourage them to complete their order."
                )
            )
        elif email_sent:
            self.hangup(
                final_instructions=(
                    "Let them know a link to their cart has been sent to their email address. "
                    "They can click it to complete their purchase anytime. "
                    "Thank them and wish them a great day."
                )
            )
        else:
            checkout = self._checkout
            recovery_url = checkout.get("abandoned_checkout_url", "") if checkout else ""
            self.hangup(
                final_instructions=(
                    "Let them know they can complete their purchase by visiting kestrelgoods.com and logging in. "
                    + (f"Their cart link is: {recovery_url}. " if recovery_url else "")
                    + "Thank them and wish them a great day."
                )
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout-token", required=True, help="Shopify abandoned checkout token")
    parser.add_argument("--customer-name", required=True, help="Customer's first name")
    parser.add_argument("--phone", required=True, help="Customer phone number to call")
    args = parser.parse_args()

    guava.Client().create_outbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        customer_number=args.phone,
        controller_class=AbandonedCartRecoveryController,
        controller_args={
            "checkout_token": args.checkout_token,
            "customer_name": args.customer_name,
        },
    )
