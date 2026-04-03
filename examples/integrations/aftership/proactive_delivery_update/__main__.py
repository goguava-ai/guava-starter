import guava
import os
import logging
import argparse
import requests

logging.basicConfig(level=logging.INFO)

AFTERSHIP_API_KEY = os.environ["AFTERSHIP_API_KEY"]
HEADERS = {
    "as-api-key": AFTERSHIP_API_KEY,
    "Content-Type": "application/json",
}
BASE_URL = "https://api.aftership.com/v4"


def get_tracking(slug: str, tracking_number: str) -> dict | None:
    resp = requests.get(
        f"{BASE_URL}/trackings/{slug}/{tracking_number}",
        headers=HEADERS,
        timeout=10,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json().get("data", {}).get("tracking")


def add_tracking_note(slug: str, tracking_number: str, note: str) -> None:
    try:
        requests.put(
            f"{BASE_URL}/trackings/{slug}/{tracking_number}",
            headers=HEADERS,
            json={"tracking": {"note": note}},
            timeout=10,
        )
    except Exception as e:
        logging.warning("Could not update tracking note: %s", e)


class ProactiveDeliveryUpdateController(guava.CallController):
    def __init__(
        self,
        customer_name: str,
        tracking_number: str,
        slug: str,
        order_description: str,
    ):
        super().__init__()
        self.customer_name = customer_name
        self.tracking_number = tracking_number
        self.slug = slug
        self.order_description = order_description

        self.set_persona(
            organization_name="Meridian Commerce",
            agent_name="Alex",
            agent_purpose=(
                "to proactively notify Meridian Commerce customers that their package "
                "is out for delivery today"
            ),
        )

        self.reach_person(
            contact_full_name=customer_name,
            on_success=self.deliver_notification,
            on_failure=self.recipient_unavailable,
        )

    def deliver_notification(self):
        carrier = self.slug.replace("-", " ").title()

        self.set_task(
            objective=(
                f"Notify {self.customer_name} that their package is out for delivery today "
                "and confirm any delivery instructions."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.customer_name}! This is Alex calling from Meridian Commerce. "
                    f"Great news — your {self.order_description} is out for delivery with "
                    f"{carrier} today. You can expect it to arrive sometime today."
                ),
                guava.Field(
                    key="delivery_instructions",
                    field_type="text",
                    description=(
                        "Ask if they have any special delivery instructions — for example, "
                        "leaving the package at a side door, with a neighbor, or in a mailroom. "
                        "Note their preference. If they have no special instructions, that's fine."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="will_be_home",
                    field_type="multiple_choice",
                    description=(
                        "Ask if someone will be home to receive the package, or if they're "
                        "comfortable with it being left if they're not."
                    ),
                    choices=[
                        "yes, someone will be home",
                        "no, but leave it at the door",
                        "no — please have carrier hold for pickup",
                    ],
                    required=True,
                ),
            ],
            on_complete=self.record_and_close,
        )

    def record_and_close(self):
        instructions = self.get_field("delivery_instructions") or ""
        will_be_home = self.get_field("will_be_home") or "yes, someone will be home"

        logging.info(
            "Delivery update for tracking %s: will_be_home=%s",
            self.tracking_number, will_be_home,
        )

        note = f"Out-for-delivery call: {will_be_home}."
        if instructions:
            note += f" Delivery instructions: {instructions}"
        add_tracking_note(self.slug, self.tracking_number, note)

        if will_be_home == "no — please have carrier hold for pickup":
            self.hangup(
                final_instructions=(
                    f"Let {self.customer_name} know you'll note their preference to have the "
                    "carrier hold the package. Explain that they should also contact "
                    f"the carrier directly to arrange this, as we can't guarantee the carrier "
                    "will intercept in time. Wish them a great day."
                )
            )
        else:
            closing = (
                f" Their delivery instructions have been noted: {instructions}."
                if instructions
                else ""
            )
            self.hangup(
                final_instructions=(
                    f"Wrap up warmly with {self.customer_name}. Let them know to keep an eye "
                    f"out for their delivery today.{closing} "
                    "Remind them they can track their package on the Meridian Commerce website. "
                    "Wish them a great day."
                )
            )

    def recipient_unavailable(self):
        logging.info(
            "Unable to reach %s for out-for-delivery notification on %s",
            self.customer_name, self.tracking_number,
        )
        self.hangup(
            final_instructions=(
                f"Leave a brief, upbeat voicemail for {self.customer_name} from Meridian Commerce. "
                f"Let them know their {self.order_description} is out for delivery today "
                "and to keep an eye out. Keep it under 20 seconds."
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Outbound out-for-delivery notification call."
    )
    parser.add_argument("phone", help="Customer phone number (E.164, e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Customer full name")
    parser.add_argument("--tracking-number", required=True, help="Shipment tracking number")
    parser.add_argument("--slug", required=True, help="Carrier slug (e.g. ups, fedex, usps)")
    parser.add_argument(
        "--order-description",
        default="order",
        help="Short description of what's in the shipment (e.g. 'blue running shoes')",
    )
    args = parser.parse_args()

    logging.info(
        "Calling %s (%s) — out for delivery on tracking %s",
        args.name, args.phone, args.tracking_number,
    )

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=ProactiveDeliveryUpdateController(
            customer_name=args.name,
            tracking_number=args.tracking_number,
            slug=args.slug,
            order_description=args.order_description,
        ),
    )
