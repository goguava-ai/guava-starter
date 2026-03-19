import guava
import os
import logging
import json
import argparse
from datetime import datetime

logging.basicConfig(level=logging.INFO)


class LeaseEndOutreachController(guava.CallController):
    def __init__(self, customer_name, vehicle, lease_end_date, buyout_price):
        super().__init__()
        self.customer_name = customer_name
        self.vehicle = vehicle
        self.lease_end_date = lease_end_date
        self.buyout_price = buyout_price

        self.set_persona(
            organization_name="Lakeside Auto Group - Finance",
            agent_name="Riley",
            agent_purpose=(
                "contact lessees approaching the end of their lease term to discuss "
                "their options — returning the vehicle, purchasing it, or re-leasing — "
                "and collect their decision so the finance team can prepare accordingly"
            ),
        )

        self.reach_person(
            contact_full_name=self.customer_name,
            on_success=self.start_lease_end_outreach,
            on_failure=self.recipient_unavailable,
        )

    def start_lease_end_outreach(self):
        self.set_task(
            objective=(
                f"Reach out to {self.customer_name} whose lease on their {self.vehicle} "
                f"ends on {self.lease_end_date}. Walk them through the three options: "
                f"returning the vehicle, buying it out (buyout price: {self.buyout_price}), "
                f"or re-leasing a new vehicle. Collect their decision and any relevant "
                f"preferences so the Lakeside Auto Group finance team can follow up."
            ),
            checklist=[
                guava.Say(
                    f"Inform {self.customer_name} that their lease on the {self.vehicle} "
                    f"is ending on {self.lease_end_date} and that Lakeside Auto Group - "
                    f"Finance is reaching out to help them explore their next steps: "
                    f"returning the vehicle, purchasing it for {self.buyout_price}, or "
                    f"re-leasing a new model."
                ),
                guava.Field(
                    key="lease_end_decision",
                    description=(
                        "The customer's current decision or preference: return the vehicle, "
                        "buy it out, re-lease a new vehicle, or undecided"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="buyout_interest_confirmed",
                    description=(
                        "If the customer is interested in buying out the vehicle, confirm "
                        "they understand the buyout price and want the finance team to "
                        "prepare paperwork"
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="new_vehicle_interest",
                    description=(
                        "If the customer is considering re-leasing or returning, whether "
                        "they are interested in exploring new vehicle options at the dealership"
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="re_lease_model_preference",
                    description=(
                        "If the customer wants to re-lease, the make, model, or vehicle "
                        "type they are interested in"
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="appointment_requested",
                    description=(
                        "Whether the customer would like to schedule an appointment with "
                        "the finance team to finalize their decision"
                    ),
                    field_type="text",
                    required=True,
                ),
            ],
            on_complete=self.save_results,
        )

    def save_results(self):
        results = {
            "timestamp": datetime.now().isoformat(),
            "customer_name": self.customer_name,
            "vehicle": self.vehicle,
            "lease_end_date": self.lease_end_date,
            "buyout_price": self.buyout_price,
            "lease_end_decision": self.get_field("lease_end_decision"),
            "buyout_interest_confirmed": self.get_field("buyout_interest_confirmed"),
            "new_vehicle_interest": self.get_field("new_vehicle_interest"),
            "re_lease_model_preference": self.get_field("re_lease_model_preference"),
            "appointment_requested": self.get_field("appointment_requested"),
        }

        print(json.dumps(results, indent=2))
        logging.info("Lease-end outreach results collected for %s", self.customer_name)

        self.hangup(
            final_instructions=(
                f"Thank {self.customer_name} for their time. Let them know a member of "
                f"the Lakeside Auto Group finance team will follow up with next steps based "
                f"on their decision. If they requested an appointment, confirm it will be "
                f"scheduled shortly. Wish them a great day."
            )
        )

    def recipient_unavailable(self):
        logging.warning("Could not reach %s for lease-end outreach call.", self.customer_name)
        results = {
            "timestamp": datetime.now().isoformat(),
            "customer_name": self.customer_name,
            "vehicle": self.vehicle,
            "lease_end_date": self.lease_end_date,
            "buyout_price": self.buyout_price,
            "status": "recipient_unavailable",
        }
        print(json.dumps(results, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Outbound lease-end outreach call for Lakeside Auto Group Finance"
    )
    parser.add_argument("phone", help="Customer phone number to call")
    parser.add_argument("--name", required=True, help="Customer full name")
    parser.add_argument(
        "--vehicle",
        required=True,
        help='Vehicle year, make, and model (e.g. "2021 Toyota Camry")',
    )
    parser.add_argument("--lease-end-date", required=True, help="Date the lease term ends")
    parser.add_argument(
        "--buyout-price",
        default="available upon request",
        help="Vehicle buyout price (default: available upon request)",
    )
    args = parser.parse_args()

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=LeaseEndOutreachController(
            customer_name=args.name,
            vehicle=args.vehicle,
            lease_end_date=args.lease_end_date,
            buyout_price=args.buyout_price,
        ),
    )
