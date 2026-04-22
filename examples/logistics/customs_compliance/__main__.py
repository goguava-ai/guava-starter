import argparse
import json
import logging
import os
from datetime import datetime, timezone

import guava
from guava import logging_utils

agent = guava.Agent(
    name="Riley",
    organization="SwiftShip Logistics - Customs & Compliance",
    purpose=(
        "contact the shipper or broker to gather missing documentation details "
        "required for customs clearance"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(contact_full_name=call.get_variable("contact_name"))


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    contact_name = call.get_variable("contact_name")
    shipment_number = call.get_variable("shipment_number")
    missing_docs = call.get_variable("missing_docs")

    if outcome == "unavailable":
        logging.warning(
            f"Could not reach {contact_name} for customs compliance check on shipment {shipment_number}."
        )
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "shipment_number": shipment_number,
            "contact_name": contact_name,
            "missing_docs": missing_docs,
            "status": "recipient_unavailable",
        }
        print(json.dumps(results, indent=2))
        call.hangup(
            final_instructions=(
                f"Leave a voicemail for {contact_name} explaining that SwiftShip Logistics "
                f"Customs and Compliance is calling about shipment number {shipment_number}, "
                f"which is currently on hold pending the following: {missing_docs}. "
                "Ask them to call back or email the compliance team as soon as possible to avoid "
                "further delays in clearance."
            )
        )
    elif outcome == "available":
        call.set_task(
            "customs_compliance_check",
            objective=(
                f"Connect with {contact_name} regarding shipment number {shipment_number}. "
                f"The following documentation is currently missing or incomplete: {missing_docs}. "
                "Confirm commercial invoice status, collect country of origin, HS tariff code if available, "
                "total declared value, whether dangerous goods are present, and whether any additional "
                "supporting documents can be provided to complete customs clearance."
            ),
            checklist=[
                guava.Say(
                    f"Hi {contact_name}, I'm calling from SwiftShip Logistics Customs and Compliance. "
                    f"We're contacting you regarding shipment number {shipment_number}. "
                    f"We have a hold on this shipment pending the following documentation: {missing_docs}. "
                    "I'd like to go through a few quick questions to help get this cleared."
                ),
                guava.Field(
                    key="commercial_invoice_confirmed",
                    description="Whether the shipper or broker confirms a commercial invoice has been or can be provided for this shipment",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="country_of_origin",
                    description="The country where the goods being shipped were manufactured or produced",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="hs_tariff_code",
                    description="The Harmonized System tariff classification code for the goods in this shipment",
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="total_declared_value",
                    description="The total declared customs value of the shipment, including currency",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="dangerous_goods_present",
                    description="Whether the shipment contains any dangerous goods, hazardous materials, or restricted items",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="additional_documents_available",
                    description="Any additional supporting documents the shipper or broker can provide to assist with customs clearance, such as certificates of origin or packing lists",
                    field_type="text",
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("customs_compliance_check")
def on_done(call: guava.Call) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "shipment_number": call.get_variable("shipment_number"),
        "contact_name": call.get_variable("contact_name"),
        "missing_docs": call.get_variable("missing_docs"),
        "commercial_invoice_confirmed": call.get_field("commercial_invoice_confirmed"),
        "country_of_origin": call.get_field("country_of_origin"),
        "hs_tariff_code": call.get_field("hs_tariff_code"),
        "total_declared_value": call.get_field("total_declared_value"),
        "dangerous_goods_present": call.get_field("dangerous_goods_present"),
        "additional_documents_available": call.get_field("additional_documents_available"),
    }
    print(json.dumps(results, indent=2))
    logging.info("Customs compliance results saved.")
    call.hangup(
        final_instructions=(
            "Thank the contact for their time and for providing the documentation details. "
            "Let them know that the SwiftShip Customs and Compliance team will review the "
            "information and follow up if anything further is needed to complete clearance. "
            "Provide an estimated clearance timeline if possible and wish them a good day."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(description="SwiftShip Logistics - Customs Compliance Agent")
    parser.add_argument("phone", help="Shipper or broker phone number to call")
    parser.add_argument("--name", required=True, help="Full name of the shipper or broker contact")
    parser.add_argument("--shipment-number", required=True, help="Shipment or freight number")
    parser.add_argument(
        "--missing-docs",
        required=True,
        help="Description of the documentation that is missing or incomplete",
    )
    args = parser.parse_args()

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "contact_name": args.name,
            "shipment_number": args.shipment_number,
            "missing_docs": args.missing_docs,
        },
    )
