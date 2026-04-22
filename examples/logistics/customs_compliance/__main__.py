import guava
import os
import logging
from guava import logging_utils
import json
import argparse
from datetime import datetime, timezone



class CustomsComplianceController(guava.CallController):
    def __init__(self, contact_name, shipment_number, missing_docs):
        super().__init__()
        self.contact_name = contact_name
        self.shipment_number = shipment_number
        self.missing_docs = missing_docs

        self.set_persona(
            organization_name="SwiftShip Logistics - Customs & Compliance",
            agent_name="Riley",
            agent_purpose=(
                f"contact the shipper or broker regarding shipment number {self.shipment_number} "
                f"to gather missing documentation details required for customs clearance. "
                f"The following documentation is outstanding: {self.missing_docs}"
            ),
        )

        self.reach_person(
            contact_full_name=self.contact_name,
            on_success=self.start_compliance_check,
            on_failure=self.recipient_unavailable,
        )

    def start_compliance_check(self):
        self.set_task(
            objective=(
                f"Connect with {self.contact_name} regarding shipment number {self.shipment_number}. "
                f"The following documentation is currently missing or incomplete: {self.missing_docs}. "
                "Confirm commercial invoice status, collect country of origin, HS tariff code if available, "
                "total declared value, whether dangerous goods are present, and whether any additional "
                "supporting documents can be provided to complete customs clearance."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.contact_name}, I'm calling from SwiftShip Logistics Customs and Compliance. "
                    f"We're contacting you regarding shipment number {self.shipment_number}. "
                    f"We have a hold on this shipment pending the following documentation: {self.missing_docs}. "
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
            on_complete=self.save_results,
        )

    def save_results(self):
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "shipment_number": self.shipment_number,
            "contact_name": self.contact_name,
            "missing_docs": self.missing_docs,
            "commercial_invoice_confirmed": self.get_field("commercial_invoice_confirmed"),
            "country_of_origin": self.get_field("country_of_origin"),
            "hs_tariff_code": self.get_field("hs_tariff_code"),
            "total_declared_value": self.get_field("total_declared_value"),
            "dangerous_goods_present": self.get_field("dangerous_goods_present"),
            "additional_documents_available": self.get_field("additional_documents_available"),
        }
        print(json.dumps(results, indent=2))
        logging.info("Customs compliance results saved.")
        self.hangup(
            final_instructions=(
                "Thank the contact for their time and for providing the documentation details. "
                "Let them know that the SwiftShip Customs and Compliance team will review the "
                "information and follow up if anything further is needed to complete clearance. "
                "Provide an estimated clearance timeline if possible and wish them a good day."
            )
        )

    def recipient_unavailable(self):
        logging.warning(
            f"Could not reach {self.contact_name} for customs compliance check on shipment {self.shipment_number}."
        )
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "shipment_number": self.shipment_number,
            "contact_name": self.contact_name,
            "missing_docs": self.missing_docs,
            "status": "recipient_unavailable",
        }
        print(json.dumps(results, indent=2))
        self.hangup(
            final_instructions=(
                f"Leave a voicemail for {self.contact_name} explaining that SwiftShip Logistics "
                f"Customs and Compliance is calling about shipment number {self.shipment_number}, "
                f"which is currently on hold pending the following: {self.missing_docs}. "
                "Ask them to call back or email the compliance team as soon as possible to avoid "
                "further delays in clearance."
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

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=CustomsComplianceController(
            contact_name=args.name,
            shipment_number=args.shipment_number,
            missing_docs=args.missing_docs,
        ),
    )
