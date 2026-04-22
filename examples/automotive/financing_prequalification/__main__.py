import guava
import os
import logging
from guava import logging_utils
import json
from datetime import datetime


agent = guava.Agent(
    name="Casey",
    organization="Lakeside Auto Group - Finance",
    purpose=(
        "collect income and credit background information from prospective buyers "
        "over the phone before their dealership visit so the finance team can "
        "prepare pre-qualification options in advance"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "prequalification",
        objective=(
            "Greet the caller and let them know they have reached the Lakeside Auto "
            "Group Finance pre-qualification line. Collect their personal, vehicle, "
            "and financial details so a finance specialist can review the information "
            "and follow up with pre-qualification options before their visit."
        ),
        checklist=[
            guava.Say(
                "Welcome the caller to the Lakeside Auto Group Finance pre-qualification "
                "line. Explain that collecting a few details now will allow the finance "
                "team to prepare personalized financing options before their visit, "
                "making the process faster and easier at the dealership."
            ),
            guava.Field(
                key="full_name",
                description="The caller's full legal name",
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="vehicle_of_interest",
                description="The make, model, and year (if known) of the vehicle the caller is interested in purchasing",
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="estimated_purchase_price",
                description="The caller's estimated or target purchase price for the vehicle",
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="annual_income",
                description="The caller's total annual income before taxes",
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="employment_status",
                description=(
                    "The caller's current employment status "
                    "(e.g. full-time employed, part-time, self-employed, retired, unemployed)"
                ),
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="down_payment_amount",
                description="The amount the caller plans to put down as a down payment",
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="credit_score_range",
                description=(
                    "The caller's estimated credit score range "
                    "(e.g. below 580, 580-669, 670-739, 740-799, 800 and above)"
                ),
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="trade_in_vehicle",
                description=(
                    "Details about any vehicle the caller intends to trade in, "
                    "including year, make, model, and approximate mileage"
                ),
                field_type="text",
                required=False,
            ),
        ],
    )


@agent.on_task_complete("prequalification")
def on_prequalification_done(call: guava.Call) -> None:
    full_name = call.get_field("full_name")
    results = {
        "timestamp": datetime.now().isoformat(),
        "full_name": full_name,
        "vehicle_of_interest": call.get_field("vehicle_of_interest"),
        "estimated_purchase_price": call.get_field("estimated_purchase_price"),
        "annual_income": call.get_field("annual_income"),
        "employment_status": call.get_field("employment_status"),
        "down_payment_amount": call.get_field("down_payment_amount"),
        "credit_score_range": call.get_field("credit_score_range"),
        "trade_in_vehicle": call.get_field("trade_in_vehicle"),
    }

    print(json.dumps(results, indent=2))
    logging.info("Financing pre-qualification intake completed for %s", full_name)

    call.hangup(
        final_instructions=(
            "Thank the caller for providing their information. Let them know that a "
            "Lakeside Auto Group finance specialist will review their details and follow "
            "up with pre-qualification options before their visit. Assure them that their "
            "information is handled securely and confidentially. Wish them a great day "
            "and let them know the team looks forward to helping them find the right vehicle."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
