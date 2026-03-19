import guava
import os
import logging
import json
import argparse
from datetime import datetime

logging.basicConfig(level=logging.INFO)


class DeviceTradeInController(guava.CallController):
    def __init__(self, contact_name, account_number, current_device, trade_in_value):
        super().__init__()
        self.contact_name = contact_name
        self.account_number = account_number
        self.current_device = current_device
        self.trade_in_value = trade_in_value

        self.set_persona(
            organization_name="Nexus Mobile",
            agent_name="Sam",
            agent_purpose=(
                "to reach out to Nexus Mobile customers who are eligible for a device upgrade, "
                "share the trade-in value of their current device, gauge their interest in "
                "upgrading, and help them choose between visiting a store or using the "
                "mail-in trade-in option"
            ),
        )

        self.reach_person(
            contact_full_name=self.contact_name,
            on_success=self.begin_tradein_flow,
            on_failure=self.recipient_unavailable,
        )

    def begin_tradein_flow(self):
        self.set_task(
            objective=(
                f"You are speaking with {self.contact_name}, a Nexus Mobile customer "
                f"(account #{self.account_number}) who is eligible for a device upgrade. "
                f"Their current device is a {self.current_device}, which has an estimated "
                f"trade-in value of {self.trade_in_value}. "
                "Your goal is to let them know about this offer, understand their interest "
                "in trading in and upgrading, and if interested, collect their preferred "
                "method (store visit or mail-in) and schedule accordingly. "
                "Be enthusiastic but not pushy."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.contact_name.split()[0]}, this is Sam calling from Nexus Mobile. "
                    f"I have some great news for you — your {self.current_device} qualifies "
                    f"for our device upgrade program and we're able to offer you an estimated "
                    f"trade-in value of {self.trade_in_value} toward a brand new device. "
                    f"I just wanted to take a moment to tell you about your options."
                ),
                guava.Field(
                    key="trade_in_interested",
                    description=(
                        f"Ask the customer if they are interested in trading in their "
                        f"{self.current_device} for a new device given the estimated trade-in "
                        f"value of {self.trade_in_value}. Capture their level of interest clearly."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="current_device_condition",
                    description=(
                        "If the customer is interested, ask them to describe the current condition "
                        "of their device. Offer these options: excellent (like new, no scratches), "
                        "good (minor wear), fair (noticeable scratches or small cracks), or "
                        "poor (significant damage). Capture the condition they select or describe."
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="new_device_interest",
                    description=(
                        "Ask the customer if they have a particular new device in mind that "
                        "they would like to upgrade to, or if they would like recommendations. "
                        "Capture what they express interest in."
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="trade_in_method_preference",
                    description=(
                        "Explain the two trade-in options: visiting a Nexus Mobile store in person "
                        "where they can walk out with a new device the same day, or using the "
                        "mail-in program where a prepaid shipping kit is sent to them. "
                        "Ask which method they prefer. Capture 'store' or 'mail_in'."
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="preferred_store_visit_date",
                    description=(
                        "If the customer prefers to visit a store, ask them what date works best "
                        "for them to come in. Capture the date they provide."
                    ),
                    field_type="date",
                    required=False,
                ),
            ],
            on_complete=self.save_results,
        )

    def save_results(self):
        results = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "agent": "Sam",
            "organization": "Nexus Mobile",
            "use_case": "device_tradeins",
            "contact_name": self.contact_name,
            "account_number": self.account_number,
            "current_device": self.current_device,
            "trade_in_value": self.trade_in_value,
            "fields": {
                "trade_in_interested": self.get_field("trade_in_interested"),
                "current_device_condition": self.get_field("current_device_condition"),
                "new_device_interest": self.get_field("new_device_interest"),
                "trade_in_method_preference": self.get_field("trade_in_method_preference"),
                "preferred_store_visit_date": self.get_field("preferred_store_visit_date"),
            },
        }
        print(json.dumps(results, indent=2))
        logging.info("Device trade-in call results saved.")
        self.hangup(
            final_instructions=(
                "Thank the customer enthusiastically for their time. If they are interested "
                "in a store visit, confirm the date and let them know a Nexus Mobile specialist "
                "will be ready to assist them. If they chose mail-in, let them know a prepaid "
                "shipping kit will be sent within 2 to 3 business days. If they are not "
                "interested right now, let them know the offer stands and they can call "
                "Nexus Mobile whenever they are ready."
            )
        )

    def recipient_unavailable(self):
        results = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "agent": "Sam",
            "organization": "Nexus Mobile",
            "use_case": "device_tradeins",
            "contact_name": self.contact_name,
            "account_number": self.account_number,
            "current_device": self.current_device,
            "status": "recipient_unavailable",
        }
        print(json.dumps(results, indent=2))
        logging.info("Recipient unavailable for device trade-in call.")
        self.hangup(
            final_instructions=(
                "The contact was not available. End the call politely without leaving "
                "account details in a voicemail."
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Nexus Mobile — Device Trade-In outbound call agent"
    )
    parser.add_argument("phone", help="Customer phone number to call (E.164 format)")
    parser.add_argument("--name", required=True, help="Full name of the customer")
    parser.add_argument("--account-number", required=True, help="Customer account number")
    parser.add_argument(
        "--current-device", required=True, help="Make and model of the customer's current device"
    )
    parser.add_argument(
        "--trade-in-value",
        required=True,
        help="Estimated trade-in value for the current device (e.g. '$200')",
    )
    args = parser.parse_args()

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=DeviceTradeInController(
            contact_name=args.name,
            account_number=args.account_number,
            current_device=args.current_device,
            trade_in_value=args.trade_in_value,
        ),
    )
