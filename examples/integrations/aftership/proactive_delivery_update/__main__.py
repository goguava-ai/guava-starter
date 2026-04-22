import guava
import os
import logging
from guava import logging_utils
import argparse
import requests


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


agent = guava.Agent(
    name="Alex",
    organization="Meridian Commerce",
    purpose=(
        "to proactively notify Meridian Commerce customers that their package "
        "is out for delivery today"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(contact_full_name=call.get_variable("customer_name"))


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    if outcome == "unavailable":
        logging.info(
            "Unable to reach %s for out-for-delivery notification on %s",
            call.get_variable("customer_name"), call.get_variable("tracking_number"),
        )
        call.hangup(
            final_instructions=(
                f"Leave a brief, upbeat voicemail for {call.get_variable('customer_name')} from Meridian Commerce. "
                f"Let them know their {call.get_variable('order_description')} is out for delivery today "
                "and to keep an eye out. Keep it under 20 seconds."
            )
        )
    elif outcome == "available":
        customer_name = call.get_variable("customer_name")
        tracking_number = call.get_variable("tracking_number")
        slug = call.get_variable("slug")
        order_description = call.get_variable("order_description")
        carrier = slug.replace("-", " ").title()

        call.set_task(
            "deliver_out_for_delivery_notification",
            objective=(
                f"Notify {customer_name} that their package is out for delivery today "
                "and confirm any delivery instructions."
            ),
            checklist=[
                guava.Say(
                    f"Hi {customer_name}! This is Alex calling from Meridian Commerce. "
                    f"Great news — your {order_description} is out for delivery with "
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
        )


@agent.on_task_complete("deliver_out_for_delivery_notification")
def on_done(call: guava.Call) -> None:
    instructions = call.get_field("delivery_instructions") or ""
    will_be_home = call.get_field("will_be_home") or "yes, someone will be home"
    customer_name = call.get_variable("customer_name")
    tracking_number = call.get_variable("tracking_number")
    slug = call.get_variable("slug")

    logging.info(
        "Delivery update for tracking %s: will_be_home=%s",
        tracking_number, will_be_home,
    )

    note = f"Out-for-delivery call: {will_be_home}."
    if instructions:
        note += f" Delivery instructions: {instructions}"
    add_tracking_note(slug, tracking_number, note)

    if will_be_home == "no — please have carrier hold for pickup":
        call.hangup(
            final_instructions=(
                f"Let {customer_name} know you'll note their preference to have the "
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
        call.hangup(
            final_instructions=(
                f"Wrap up warmly with {customer_name}. Let them know to keep an eye "
                f"out for their delivery today.{closing} "
                "Remind them they can track their package on the Meridian Commerce website. "
                "Wish them a great day."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
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

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "customer_name": args.name,
            "tracking_number": args.tracking_number,
            "slug": args.slug,
            "order_description": args.order_description,
        },
    )
