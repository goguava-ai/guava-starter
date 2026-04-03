import guava
import os
import logging
import requests
from datetime import datetime

logging.basicConfig(level=logging.INFO)

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


class ShippingIssueController(guava.CallController):
    def __init__(self):
        super().__init__()
        self.order = None
        self.shipment = None

        self.set_persona(
            organization_name="Coastal Supply Co.",
            agent_name="Sam",
            agent_purpose=(
                "to help Coastal Supply Co. customers report and resolve issues with their shipments, "
                "including lost, damaged, delayed, or incorrect orders"
            ),
        )

        self.set_task(
            objective=(
                "A customer has called to report a problem with their shipment. "
                "Greet them, collect their order information and the nature of the issue, "
                "then gather the details needed to resolve it."
            ),
            checklist=[
                guava.Say(
                    "Thanks for calling Coastal Supply Co. I'm Sam, and I'm here to help you "
                    "sort out your shipment issue. Let me pull up your order."
                ),
                guava.Field(
                    key="order_number",
                    field_type="text",
                    description=(
                        "Ask for their order number. If they don't have it, "
                        "ask for the email address on their account."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="email",
                    field_type="text",
                    description=(
                        "If they provided an email address instead of an order number above, "
                        "confirm it here. Skip if they already gave an order number."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="issue_type",
                    field_type="multiple_choice",
                    description="Ask what type of issue they are experiencing with their shipment.",
                    choices=[
                        "package is lost",
                        "package arrived damaged",
                        "package is delayed",
                        "wrong items received",
                    ],
                    required=True,
                ),
            ],
            on_complete=self.lookup_order_and_route,
        )

        self.accept_call()

    def lookup_order_and_route(self):
        order_number = self.get_field("order_number")
        email = self.get_field("email")
        issue_type = self.get_field("issue_type") or ""

        # Look up the order by order number or email.
        try:
            if order_number and "@" not in order_number:
                resp = requests.get(
                    f"{BASE_URL}/orders",
                    auth=AUTH,
                    params={"orderNumber": order_number},
                    timeout=10,
                )
                resp.raise_for_status()
                orders = resp.json().get("orders", [])
                if orders:
                    self.order = orders[0]
            else:
                lookup_email = email or order_number
                resp = requests.get(
                    f"{BASE_URL}/orders",
                    auth=AUTH,
                    params={"customerEmail": lookup_email, "orderStatus": "shipped"},
                    timeout=10,
                )
                resp.raise_for_status()
                orders = resp.json().get("orders", [])
                if orders:
                    self.order = orders[0]
        except Exception as e:
            logging.error("Failed to look up order in ShipStation: %s", e)

        if not self.order:
            self.hangup(
                final_instructions=(
                    "Apologize and let the customer know we couldn't locate an order with the "
                    "information they provided. Ask them to try again with a different order number "
                    "or email, or to email support@coastalsupply.com. "
                    "Thank them for calling Coastal Supply Co."
                )
            )
            return

        # Fetch shipment details.
        order_id = self.order.get("orderId")
        try:
            resp = requests.get(
                f"{BASE_URL}/shipments",
                auth=AUTH,
                params={"orderId": order_id},
                timeout=10,
            )
            resp.raise_for_status()
            shipments = resp.json().get("shipments", [])
            active = [s for s in shipments if not s.get("voided", False)]
            if active:
                self.shipment = active[0]
        except Exception as e:
            logging.error("Failed to fetch shipments for order %s: %s", order_id, e)

        logging.info(
            "Order %s found. Issue type: %s. Shipment found: %s",
            order_id,
            issue_type,
            bool(self.shipment),
        )

        # Route to the appropriate collection flow based on issue type.
        if "lost" in issue_type or "damaged" in issue_type:
            self.collect_claim_details()
        elif "delayed" in issue_type:
            self.handle_delayed()
        elif "wrong" in issue_type:
            self.collect_wrong_item_details()
        else:
            self.collect_claim_details()

    def collect_claim_details(self):
        issue_type = self.get_field("issue_type") or "issue"
        order_num_display = self.order.get("orderNumber", "your order")

        self.set_task(
            objective=(
                f"The customer is reporting that their {issue_type}. "
                "Collect a brief description of what happened and their preferred resolution."
            ),
            checklist=[
                guava.Say(
                    f"I'm sorry to hear that — a {issue_type} is definitely something we'll "
                    f"take care of for you. I have a few more questions about order {order_num_display}."
                ),
                guava.Field(
                    key="description",
                    field_type="text",
                    description=(
                        "Ask the customer to briefly describe what happened — "
                        "for example, when they noticed the problem, what the condition of the "
                        "package was, or what items appear to be missing or damaged."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="preferred_resolution",
                    field_type="multiple_choice",
                    description=(
                        "Ask the customer how they would like us to resolve this for them."
                    ),
                    choices=["replacement shipment", "full refund", "store credit"],
                    required=True,
                ),
            ],
            on_complete=self.finalize_claim,
        )

    def finalize_claim(self):
        issue_type = self.get_field("issue_type") or "issue"
        description = self.get_field("description") or ""
        resolution = self.get_field("preferred_resolution") or "replacement shipment"
        order_num_display = self.order.get("orderNumber", "your order")

        logging.info(
            "Claim filed for order %s — issue: %s, resolution: %s, description: %s",
            self.order.get("orderId"),
            issue_type,
            resolution,
            description,
        )

        self.hangup(
            final_instructions=(
                f"Let the customer know their claim for order {order_num_display} has been "
                f"recorded and they've requested a {resolution}. "
                "Tell them our claims team will reach out within 1 business day to follow up "
                "and get their issue fully resolved. "
                "Apologize again for the inconvenience and thank them for their patience. "
                "Thank them for calling Coastal Supply Co. and wish them a great day."
            )
        )

    def handle_delayed(self):
        order_num_display = self.order.get("orderNumber", "your order")

        tracking_info = ""
        if self.shipment:
            tracking_number = self.shipment.get("trackingNumber", "")
            carrier_code = self.shipment.get("carrierCode", "")
            ship_date_raw = self.shipment.get("shipDate", "")
            carrier_display = carrier_code.upper().replace("_", " ")

            ship_date_display = ship_date_raw
            if ship_date_raw:
                try:
                    dt = datetime.fromisoformat(ship_date_raw.replace("Z", "+00:00"))
                    ship_date_display = dt.strftime("%B %-d, %Y")
                except (ValueError, AttributeError):
                    pass

            tracking_url = get_tracking_url(carrier_code, tracking_number)
            url_part = f" Track it at: {tracking_url}" if tracking_url else ""

            tracking_info = (
                f" Your order shipped via {carrier_display} on {ship_date_display}. "
                f"Tracking number: {tracking_number}.{url_part}"
            )
        else:
            tracking_info = " We don't have a tracking record on file yet for this order."

        logging.info(
            "Delayed shipment inquiry for order %s.",
            self.order.get("orderId"),
        )

        self.hangup(
            final_instructions=(
                f"Let the customer know their order {order_num_display} appears to be delayed.{tracking_info} "
                "Encourage them to check the tracking link for the latest status from the carrier. "
                "Let them know that if the package does not arrive within 2 more business days, "
                "they should call back or email support@coastalsupply.com and we will open a trace "
                "with the carrier. "
                "Apologize for the delay and thank them for their patience. "
                "Thank them for calling Coastal Supply Co."
            )
        )

    def collect_wrong_item_details(self):
        order_num_display = self.order.get("orderNumber", "your order")

        self.set_task(
            objective=(
                f"The customer received wrong items in order {order_num_display}. "
                "Collect a description of what they received versus what they ordered."
            ),
            checklist=[
                guava.Say(
                    f"I'm sorry about that — receiving the wrong items is definitely not what "
                    f"we want. I'll make sure we get this sorted out for order {order_num_display}."
                ),
                guava.Field(
                    key="wrong_item_description",
                    field_type="text",
                    description=(
                        "Ask the customer to describe what they received that was incorrect — "
                        "for example, the wrong size, color, product, or quantity. "
                        "Capture their description."
                    ),
                    required=True,
                ),
            ],
            on_complete=self.finalize_wrong_item,
        )

    def finalize_wrong_item(self):
        wrong_item_description = self.get_field("wrong_item_description") or ""
        order_num_display = self.order.get("orderNumber", "your order")

        logging.info(
            "Wrong items reported for order %s — description: %s",
            self.order.get("orderId"),
            wrong_item_description,
        )

        self.hangup(
            final_instructions=(
                f"Let the customer know their report for order {order_num_display} has been "
                "recorded and our fulfillment team will send the correct replacement items right away. "
                "Tell them they'll receive a new shipping confirmation by email once the replacement "
                "is dispatched, typically within 1 business day. "
                "They do not need to return the incorrect items unless contacted by our team. "
                "Apologize again for the mix-up and thank them for calling Coastal Supply Co."
            )
        )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=ShippingIssueController,
    )
