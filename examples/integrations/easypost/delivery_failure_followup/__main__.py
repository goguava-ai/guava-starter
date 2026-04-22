import guava
import os
import logging
from guava import logging_utils
import argparse
import requests


EASYPOST_API_KEY = os.environ["EASYPOST_API_KEY"]
BASE_URL = "https://api.easypost.com/v2"


def fetch_tracker(tracking_code: str) -> dict | None:
    try:
        resp = requests.get(
            f"{BASE_URL}/trackers",
            auth=(EASYPOST_API_KEY, ""),
            params={"tracking_code": tracking_code},
            timeout=10,
        )
        resp.raise_for_status()
        trackers = resp.json().get("trackers", [])
        return trackers[0] if trackers else None
    except Exception as e:
        logging.error("EasyPost error fetching tracker for %s: %s", tracking_code, e)
        return None


def create_address(street1: str, city: str, state: str, zip_code: str, country: str = "US") -> dict | None:
    try:
        payload = {
            "address": {
                "street1": street1,
                "city": city,
                "state": state,
                "zip": zip_code,
                "country": country,
            },
            "verify": ["delivery"],
        }
        resp = requests.post(
            f"{BASE_URL}/addresses",
            auth=(EASYPOST_API_KEY, ""),
            json=payload,
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logging.error("EasyPost error creating address: %s", e)
        return None


class DeliveryFailureFollowupController(guava.CallController):
    def __init__(self, customer_name: str, tracking_code: str, order_number: str):
        super().__init__()
        self.customer_name = customer_name
        self.tracking_code = tracking_code
        self.order_number = order_number

        try:
            self.tracker = fetch_tracker(tracking_code)
        except Exception as e:
            logging.error("Pre-fetch failed: %s", e)
            self.tracker = None

        status = self.tracker.get("status", "unknown") if self.tracker else "unknown"
        carrier = self.tracker.get("carrier", "the carrier") if self.tracker else "the carrier"
        self.status = status
        self.carrier = carrier

        self.set_persona(
            organization_name="Summit Outfitters",
            agent_name="Alex",
            agent_purpose="to reach customers about delivery issues with their orders and arrange resolution",
        )

        self.reach_person(
            contact_full_name=self.customer_name,
            on_success=self.begin_call,
            on_failure=self.recipient_unavailable,
        )

    def begin_call(self):
        self.set_task(
            objective=(
                f"Inform {self.customer_name} that their package (order {self.order_number}) "
                f"encountered a delivery issue and has a status of '{self.status}'. "
                "Collect a corrected shipping address and confirm how they would like to proceed."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.customer_name}, this is Alex calling from Summit Outfitters regarding your recent order, number {self.order_number}. "
                    f"I'm calling because we received a notification that your package had a delivery issue with {self.carrier} and could not be delivered as expected."
                ),
                guava.Field(
                    key="issue_acknowledged",
                    field_type="multiple_choice",
                    description="Ask if the customer is aware of the delivery issue and whether they have any context on what happened.",
                    choices=["yes, aware of the issue", "no, this is news to me"],
                    required=True,
                ),
                guava.Field(
                    key="correct_street",
                    field_type="text",
                    description="Ask the customer to provide the correct street address (including apartment or suite number if applicable) where they would like the package re-shipped.",
                    required=True,
                ),
                guava.Field(
                    key="correct_city",
                    field_type="text",
                    description="Ask for the city for the corrected address.",
                    required=True,
                ),
                guava.Field(
                    key="correct_state",
                    field_type="text",
                    description="Ask for the state (two-letter abbreviation) for the corrected address.",
                    required=True,
                ),
                guava.Field(
                    key="correct_zip",
                    field_type="text",
                    description="Ask for the ZIP code for the corrected address.",
                    required=True,
                ),
                guava.Field(
                    key="resolution_preference",
                    field_type="multiple_choice",
                    description=(
                        "Explain the two options available: re-ship the package to their corrected address at no charge, "
                        "or issue a full refund. Ask how they would like to proceed."
                    ),
                    choices=["reship to new address", "issue full refund"],
                    required=True,
                ),
            ],
            on_complete=self.handle_outcome,
        )

    def handle_outcome(self):
        street = self.get_field("correct_street")
        city = self.get_field("correct_city")
        state = self.get_field("correct_state")
        zip_code = self.get_field("correct_zip")
        resolution = self.get_field("resolution_preference")

        address_result = None
        address_valid = False

        if resolution == "reship to new address":
            address_result = create_address(street, city, state, zip_code)
            if address_result:
                verifications = address_result.get("verifications", {})
                delivery = verifications.get("delivery", {})
                address_valid = delivery.get("success", False)
            else:
                address_valid = False

        if resolution == "reship to new address" and address_valid:
            self.hangup(
                final_instructions=(
                    f"Thank {self.customer_name} and confirm that their replacement shipment will be sent to "
                    f"{street}, {city}, {state} {zip_code}. "
                    "Let them know they will receive a new tracking number by email within one business day. "
                    "Apologize for the inconvenience and express appreciation for their patience. Be warm and professional."
                )
            )
        elif resolution == "reship to new address" and not address_valid:
            self.hangup(
                final_instructions=(
                    f"Tell {self.customer_name} that the address they provided could not be verified. "
                    "Ask them to double-check the address and call back, or visit the website to update their shipping address. "
                    "Apologize for the inconvenience and assure them a team member will follow up. Be helpful and understanding."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Confirm to {self.customer_name} that a full refund for order {self.order_number} will be processed "
                    "to their original payment method within 5 to 7 business days. "
                    "Apologize for the delivery issue and thank them for their understanding. Be warm and sincere."
                )
            )

    def recipient_unavailable(self):
        self.hangup(
            final_instructions=(
                f"Leave a brief, professional voicemail for {self.customer_name}. "
                f"Mention you are calling from Summit Outfitters about order {self.order_number}, "
                "which encountered a delivery issue. Ask them to call back at their earliest convenience "
                "or visit the website to update their shipping address. Do not leave sensitive details."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound call for delivery failure follow-up"
    )
    parser.add_argument("phone", help="Customer phone number in E.164 format (e.g. +15551234567)")
    parser.add_argument("--tracking-code", required=True, help="EasyPost tracking code")
    parser.add_argument("--name", required=True, help="Customer full name")
    parser.add_argument("--order-number", required=True, help="Internal order number")
    args = parser.parse_args()

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=DeliveryFailureFollowupController(
            customer_name=args.name,
            tracking_code=args.tracking_code,
            order_number=args.order_number,
        ),
    )
