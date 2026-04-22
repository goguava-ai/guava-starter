import argparse
import json
import logging
import os
from datetime import datetime

import guava
from guava import logging_utils

agent = guava.Agent(
    name="Riley",
    organization="Lakeside Auto Group - Finance",
    purpose=(
        "contact lessees approaching the end of their lease term to discuss "
        "their options — returning the vehicle, purchasing it, or re-leasing — "
        "and collect their decision so the finance team can prepare accordingly"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(contact_full_name=call.get_variable("customer_name"))


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    customer_name = call.get_variable("customer_name")
    vehicle = call.get_variable("vehicle")
    lease_end_date = call.get_variable("lease_end_date")
    buyout_price = call.get_variable("buyout_price")

    if outcome == "unavailable":
        logging.warning("Could not reach %s for lease-end outreach call.", customer_name)
        results = {
            "timestamp": datetime.now().isoformat(),
            "customer_name": customer_name,
            "vehicle": vehicle,
            "lease_end_date": lease_end_date,
            "buyout_price": buyout_price,
            "status": "recipient_unavailable",
        }
        print(json.dumps(results, indent=2))
        call.hangup()
    elif outcome == "available":
        call.set_task(
            "lease_end_outreach",
            objective=(
                f"Reach out to {customer_name} whose lease on their {vehicle} "
                f"ends on {lease_end_date}. Walk them through the three options: "
                f"returning the vehicle, buying it out (buyout price: {buyout_price}), "
                f"or re-leasing a new vehicle. Collect their decision and any relevant "
                f"preferences so the Lakeside Auto Group finance team can follow up."
            ),
            checklist=[
                guava.Say(
                    f"Inform {customer_name} that their lease on the {vehicle} "
                    f"is ending on {lease_end_date} and that Lakeside Auto Group - "
                    f"Finance is reaching out to help them explore their next steps: "
                    f"returning the vehicle, purchasing it for {buyout_price}, or "
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
        )


@agent.on_task_complete("lease_end_outreach")
def on_lease_end_outreach_done(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    results = {
        "timestamp": datetime.now().isoformat(),
        "customer_name": customer_name,
        "vehicle": call.get_variable("vehicle"),
        "lease_end_date": call.get_variable("lease_end_date"),
        "buyout_price": call.get_variable("buyout_price"),
        "lease_end_decision": call.get_field("lease_end_decision"),
        "buyout_interest_confirmed": call.get_field("buyout_interest_confirmed"),
        "new_vehicle_interest": call.get_field("new_vehicle_interest"),
        "re_lease_model_preference": call.get_field("re_lease_model_preference"),
        "appointment_requested": call.get_field("appointment_requested"),
    }

    print(json.dumps(results, indent=2))
    logging.info("Lease-end outreach results collected for %s", customer_name)

    call.hangup(
        final_instructions=(
            f"Thank {customer_name} for their time. Let them know a member of "
            f"the Lakeside Auto Group finance team will follow up with next steps based "
            f"on their decision. If they requested an appointment, confirm it will be "
            f"scheduled shortly. Wish them a great day."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
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

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "customer_name": args.name,
            "vehicle": args.vehicle,
            "lease_end_date": args.lease_end_date,
            "buyout_price": args.buyout_price,
        },
    )
