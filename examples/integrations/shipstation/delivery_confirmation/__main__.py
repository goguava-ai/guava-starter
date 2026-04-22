import argparse
import logging
import os
from datetime import datetime

import guava
import requests
from guava import logging_utils

BASE_URL = "https://ssapi.shipstation.com"
AUTH = (os.environ["SHIPSTATION_API_KEY"], os.environ["SHIPSTATION_API_SECRET"])

TRACKING_URLS = {
    "ups": "https://www.ups.com/track?tracknum={tracking_number}",
    "usps": "https://tools.usps.com/go/TrackConfirmAction?tLabels={tracking_number}",
    "fedex": "https://www.fedex.com/fedextrack/?trknbr={tracking_number}",
    "dhl_express": "https://www.dhl.com/en/express/tracking.html?AWB={tracking_number}",
}


def get_tracking_url(carrier_code: str, tracking_number: str) -> str:
    template = TRACKING_URLS.get(carrier_code.lower(), "")
    if template:
        return template.format(tracking_number=tracking_number)
    return ""


agent = guava.Agent(
    name="Riley",
    organization="Coastal Supply Co.",
    purpose=(
        "to confirm delivery of recent orders and check in on customer satisfaction "
        "on behalf of Coastal Supply Co."
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    shipment_id = int(call.get_variable("shipment_id"))

    # Pre-call: fetch the shipment to get carrier and tracking details.
    # This lets the agent give the customer their tracking info if they haven't received
    # the package yet, rather than asking them to look it up themselves.
    call.set_variable("tracking_number", "")
    call.set_variable("carrier_code", "")
    call.set_variable("tracking_url", "")
    try:
        resp = requests.get(
            f"{BASE_URL}/shipments",
            auth=AUTH,
            params={"shipmentId": shipment_id},
            timeout=10,
        )
        resp.raise_for_status()
        shipments = resp.json().get("shipments", [])
        if shipments:
            shipment = shipments[0]
            tracking_number = shipment.get("trackingNumber", "")
            carrier_code = shipment.get("carrierCode", "")
            call.set_variable("tracking_number", tracking_number)
            call.set_variable("carrier_code", carrier_code)
            if tracking_number and carrier_code:
                call.set_variable("tracking_url", get_tracking_url(carrier_code, tracking_number))
            logging.info(
                "Pre-call: shipment %s — carrier: %s, tracking: %s",
                shipment_id,
                carrier_code,
                tracking_number,
            )
    except Exception as e:
        logging.error("Failed to fetch shipment %s pre-call: %s", shipment_id, e)

    call.reach_person(contact_full_name=customer_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    customer_name = call.get_variable("customer_name")
    order_number = call.get_variable("order_number")

    if outcome == "unavailable":
        call.hangup(
            final_instructions=(
                f"Leave a brief, friendly voicemail for {customer_name} on behalf of "
                "Coastal Supply Co. Let them know we were calling to confirm that order "
                f"{order_number} arrived safely and that we hope everything looks great. "
                "If they have any issues or questions, ask them to call us back or reach out "
                "at support@coastalsupply.com. No action is needed if everything is fine. "
                "Thank them for being a Coastal Supply Co. customer."
            )
        )
    elif outcome == "available":
        call.set_task(
            "handle_outcome",
            objective=(
                f"Confirm that {customer_name} received order {order_number} and "
                "collect their satisfaction rating."
            ),
            checklist=[
                guava.Say(
                    f"Hi {customer_name}, this is Riley calling from Coastal Supply Co. "
                    f"I'm following up on your recent order, {order_number}, to make sure "
                    "everything arrived as expected."
                ),
                guava.Field(
                    key="delivery_status",
                    field_type="multiple_choice",
                    description=(
                        "Ask the customer whether they received their order. "
                        "Capture their response."
                    ),
                    choices=["yes, received it", "no, haven't received it", "package was damaged"],
                    required=True,
                ),
                guava.Field(
                    key="satisfaction",
                    field_type="multiple_choice",
                    description=(
                        "If they received the order (delivery_status is 'yes, received it'), "
                        "ask how satisfied they are with their order overall. "
                        "Skip this question if they haven't received it or if it was damaged."
                    ),
                    choices=["very satisfied", "satisfied", "neutral", "dissatisfied"],
                    required=False,
                ),
                guava.Field(
                    key="wants_review",
                    field_type="multiple_choice",
                    description=(
                        "If the customer received the order and gave a satisfaction rating, "
                        "ask if they would be willing to leave a quick review on our website. "
                        "Skip if the order wasn't received or was damaged."
                    ),
                    choices=["yes", "no"],
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("handle_outcome")
def on_done(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    order_number = call.get_variable("order_number")

    delivery_status = call.get_field("delivery_status") or ""
    satisfaction = call.get_field("satisfaction") or ""
    wants_review = call.get_field("wants_review") or ""

    logging.info(
        "Delivery confirmation for order %s — status: %s, satisfaction: %s, wants_review: %s",
        order_number,
        delivery_status,
        satisfaction,
        wants_review,
    )

    if "damaged" in delivery_status.lower():
        call.hangup(
            final_instructions=(
                f"Sincerely apologize to {customer_name} that their package arrived damaged. "
                "Let them know this is being escalated to our shipping claims team right away "
                "and someone will reach out to them within 1 business day to arrange a "
                "replacement or refund. "
                "Thank them for letting us know and for their patience."
            )
        )
        return

    if "no" in delivery_status.lower() or "haven't" in delivery_status.lower():
        carrier_code = call.get_variable("carrier_code", "")
        tracking_number = call.get_variable("tracking_number", "")
        tracking_url = call.get_variable("tracking_url", "")
        carrier_display = carrier_code.upper().replace("_", " ") if carrier_code else "the carrier"
        tracking_part = ""
        if tracking_number:
            tracking_part = (
                f" Your tracking number with {carrier_display} is {tracking_number}."
            )
            if tracking_url:
                tracking_part += f" You can check the latest status at: {tracking_url}"

        call.hangup(
            final_instructions=(
                f"Let {customer_name} know their order {order_number} shows as shipped "
                f"in our system.{tracking_part} "
                "Tell them it may still be in transit and to check the tracking link for the "
                "latest carrier update. "
                "If the package does not arrive within 2 more days, ask them to call us back "
                "or email support@coastalsupply.com and we will open an investigation. "
                "Apologize for any inconvenience and thank them for calling."
            )
        )
        return

    # Package was received — handle satisfaction response.
    if "dissatisfied" in satisfaction.lower():
        call.hangup(
            final_instructions=(
                f"Thank {customer_name} sincerely for their honest feedback. "
                "Acknowledge that we fell short of their expectations. "
                "Let them know a member of our customer care team will follow up personally "
                "to make things right. "
                "Apologize and wish them a great day."
            )
        )
    elif wants_review.lower() == "yes":
        call.hangup(
            final_instructions=(
                f"Thank {customer_name} warmly for being a Coastal Supply Co. customer "
                "and for their positive feedback. "
                "Let them know they can leave a review at coastalsupply.com/reviews — "
                "it only takes a minute and means a lot to the team. "
                "Wish them a great day and let them know we're here if they ever need anything."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {customer_name} for taking the time to confirm receipt of their order. "
                "Let them know we're glad everything arrived and that Coastal Supply Co. is always "
                "here if they need anything in the future. "
                "Wish them a great day."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound delivery confirmation call for Coastal Supply Co. via ShipStation."
    )
    parser.add_argument(
        "phone",
        help="Customer phone number to call (E.164 format, e.g. +15551234567)",
    )
    parser.add_argument("--name", required=True, help="Customer's full name")
    parser.add_argument("--order-number", required=True, help="ShipStation order number")
    parser.add_argument(
        "--shipment-id", required=True, type=int, help="ShipStation shipment ID"
    )
    args = parser.parse_args()

    logging.info(
        "Initiating delivery confirmation call to %s (%s) for order %s (shipment %s)",
        args.name,
        args.phone,
        args.order_number,
        args.shipment_id,
    )

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "customer_name": args.name,
            "order_number": args.order_number,
            "shipment_id": str(args.shipment_id),
        },
    )
