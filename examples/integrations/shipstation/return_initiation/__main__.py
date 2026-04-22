import guava
import os
import logging
import requests
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)

BASE_URL = "https://ssapi.shipstation.com"
AUTH = (os.environ["SHIPSTATION_API_KEY"], os.environ["SHIPSTATION_API_SECRET"])

# Order statuses that are eligible for a return.
RETURNABLE_STATUSES = {"shipped", "delivered"}


class ReturnInitiationController(guava.CallController):
    def __init__(self):
        super().__init__()
        self.order = None
        self.shipment = None

        self.set_persona(
            organization_name="Coastal Supply Co.",
            agent_name="Morgan",
            agent_purpose=(
                "to help Coastal Supply Co. customers initiate returns and generate prepaid "
                "return shipping labels"
            ),
        )

        self.set_task(
            objective=(
                "A customer has called to start a return. "
                "Greet them, collect their order details and return information, "
                "then generate a prepaid return label for them."
            ),
            checklist=[
                guava.Say(
                    "Thanks for calling Coastal Supply Co.! I'm Morgan, and I'm here to help "
                    "you start your return. This will only take a couple of minutes."
                ),
                guava.Field(
                    key="order_number",
                    field_type="text",
                    description=(
                        "Ask for their order number. If they don't have it, "
                        "ask for the email address associated with their order."
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
                    key="return_reason",
                    field_type="multiple_choice",
                    description="Ask the customer why they would like to return their order.",
                    choices=[
                        "item not as described",
                        "defective or broken",
                        "wrong size or fit",
                        "changed my mind",
                        "received wrong item",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="preferred_resolution",
                    field_type="multiple_choice",
                    description="Ask how the customer would like us to resolve their return.",
                    choices=["full refund", "exchange for different item", "store credit"],
                    required=True,
                ),
            ],
            on_complete=self.verify_and_create_return,
        )

        self.accept_call()

    def verify_and_create_return(self):
        order_number = self.get_field("order_number")
        email = self.get_field("email")
        return_reason = self.get_field("return_reason") or ""
        preferred_resolution = self.get_field("preferred_resolution") or "full refund"

        # Look up the order to verify it exists and is eligible for return.
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
                    "Apologize and let the customer know we could not find an order matching "
                    "the information they provided. Ask them to double-check their order number "
                    "or email and try calling back, or to email returns@coastalsupply.com. "
                    "Thank them for calling Coastal Supply Co."
                )
            )
            return

        order_status = self.order.get("orderStatus", "")
        order_id = self.order.get("orderId")
        order_num_display = self.order.get("orderNumber", order_number)

        # Only shipped or delivered orders can be returned.
        if order_status not in RETURNABLE_STATUSES:
            status_phrase = {
                "awaiting_shipment": "still being prepared for shipment and hasn't shipped yet",
                "on_hold": "currently on hold",
                "cancelled": "already cancelled",
            }.get(order_status, f"in status '{order_status}'")

            self.hangup(
                final_instructions=(
                    f"Let the customer know that order {order_num_display} is {status_phrase}, "
                    "so we are not able to process a return at this time. "
                    "If they believe this is incorrect, ask them to email returns@coastalsupply.com "
                    "with their order number and our team will assist them directly. "
                    "Thank them for calling Coastal Supply Co."
                )
            )
            return

        # Fetch the shipment to get carrier and service details for the return label.
        carrier_code = "ups"
        service_code = "ups_ground"
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
                carrier_code = self.shipment.get("carrierCode", "ups") or "ups"
                service_code = self.shipment.get("serviceCode", "ups_ground") or "ups_ground"
        except Exception as e:
            logging.error("Failed to fetch shipments for order %s: %s", order_id, e)

        logging.info(
            "Return initiated for order %s (status: %s) — reason: %s, resolution: %s",
            order_id,
            order_status,
            return_reason,
            preferred_resolution,
        )

        # Generate the prepaid return label via ShipStation.
        return_tracking_number = None
        try:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            label_payload = {
                "orderId": order_id,
                "carrierCode": carrier_code,
                "serviceCode": service_code,
                "packageCode": "package",
                "confirmation": "none",
                "shipDate": today,
                "weight": {"value": 1, "units": "ounces"},
                "isReturnLabel": True,
            }
            resp = requests.post(
                f"{BASE_URL}/shipments/createlabel",
                auth=AUTH,
                json=label_payload,
                timeout=15,
            )
            resp.raise_for_status()
            label_data = resp.json()
            return_tracking_number = label_data.get("trackingNumber", "")
            logging.info(
                "Return label created for order %s — tracking: %s",
                order_id,
                return_tracking_number,
            )
        except Exception as e:
            logging.error("Failed to create return label for order %s: %s", order_id, e)

        if not return_tracking_number:
            # Label creation failed — escalate to the returns team.
            self.hangup(
                final_instructions=(
                    f"Apologize to the customer and let them know we ran into a technical issue "
                    f"generating their return label for order {order_num_display}. "
                    "Assure them that our returns team will email them a prepaid return label "
                    "within 1 business day at the email address on their account. "
                    "They do not need to call back — the label is on its way. "
                    "Provide the returns team email (returns@coastalsupply.com) as an alternative. "
                    "Apologize again for the inconvenience and thank them for their patience."
                )
            )
            return

        carrier_display = carrier_code.upper().replace("_", " ")
        resolution_phrase = {
            "full refund": "a full refund will be issued to your original payment method "
                           "within 3–5 business days of us receiving the returned item",
            "exchange for different item": "once we receive your return, our team will process "
                                           "an exchange and ship out the replacement item",
            "store credit": "once we receive your return, store credit will be added to your "
                            "account within 1–2 business days",
        }.get(preferred_resolution, f"we will process your {preferred_resolution} upon receipt")

        self.hangup(
            final_instructions=(
                f"Let the customer know their return for order {order_num_display} has been "
                "successfully initiated. "
                f"Tell them their prepaid {carrier_display} return tracking number is "
                f"{return_tracking_number}. "
                "Tell them they will receive an email with the prepaid return shipping label — "
                "they can print it, attach it to their package, and drop it off at any "
                f"{carrier_display} location. "
                f"Regarding their resolution preference, let them know: {resolution_phrase}. "
                "Thank them for shopping with Coastal Supply Co. and wish them a great day."
            )
        )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=ReturnInitiationController,
    )
