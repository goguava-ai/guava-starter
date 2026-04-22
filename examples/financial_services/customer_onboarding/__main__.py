import guava
import os
import logging
from guava import logging_utils
import json
import argparse
from datetime import datetime, timezone



class CustomerOnboardingController(guava.CallController):
    def __init__(self, contact_name: str, account_type: str):
        super().__init__()
        self.contact_name = contact_name
        self.account_type = account_type

        self.set_persona(
            organization_name="First National Bank",
            agent_name="Jamie",
            agent_purpose=(
                f"to walk a new customer through the setup of their {self.account_type}, "
                f"deliver required disclosures, and configure initial account preferences"
            ),
        )

        self.reach_person(
            contact_full_name=self.contact_name,
            on_success=self.begin_onboarding,
            on_failure=self.recipient_unavailable,
        )

    def begin_onboarding(self):
        self.set_task(
            objective=(
                f"You are onboarding {self.contact_name} as a new First National Bank customer. "
                f"They have just opened a {self.account_type}. Your goal is to welcome them, "
                f"walk them through required regulatory disclosures, collect their preferences for "
                f"paperless statements and overdraft protection, confirm their debit card delivery "
                f"address, and optionally set up a security question for their online banking "
                f"profile. Be warm, clear, and patient — many customers are unfamiliar with these "
                f"steps. Confirm each selection back to the customer before moving on."
            ),
            checklist=[
                guava.Say(
                    f"Hello {self.contact_name}, congratulations on opening your new "
                    f"{self.account_type} with First National Bank! My name is Jamie and I am "
                    f"here to help you get everything set up today. This should only take a few "
                    f"minutes, and I will walk you through each step."
                ),
                guava.Say(
                    "Before we get started with your preferences, I am required to share a few "
                    "important disclosures with you. Please listen carefully. By opening this "
                    "account, you agree to the Deposit Account Agreement and the Fee Schedule, "
                    "both of which are available on our website and will be mailed to you within "
                    "7 business days. Your deposits are insured by the FDIC up to $250,000. "
                    "Standard account terms, including any applicable monthly service fees and "
                    "minimum balance requirements, apply as outlined in your account agreement."
                ),
                guava.Field(
                    key="disclosures_acknowledged",
                    description=(
                        "Confirm that the customer has heard and acknowledged the required account "
                        "disclosures including the Deposit Account Agreement, Fee Schedule, and "
                        "FDIC insurance information. Record a brief note of their acknowledgment."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Say(
                    "Next, would you like to enroll in paperless statements? With paperless "
                    "statements, your monthly statements will be delivered securely to your email "
                    "instead of by mail. You can switch back at any time through online banking."
                ),
                guava.Field(
                    key="paperless_statements_opted_in",
                    description=(
                        "Record whether the customer chose to opt in to paperless statements. "
                        "Expected values: 'yes' to enroll or 'no' to continue receiving paper statements."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Say(
                    "Would you also like to add overdraft protection to your account? Overdraft "
                    "protection allows transactions to go through even if your balance is "
                    "temporarily low, which can help you avoid declined transactions or returned "
                    "payments. A small fee may apply per covered transaction."
                ),
                guava.Field(
                    key="overdraft_protection_opted_in",
                    description=(
                        "Record whether the customer chose to opt in to overdraft protection. "
                        "Expected values: 'yes' to enroll or 'no' to decline."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Say(
                    "Your debit card will be mailed to the address we have on file. I want to "
                    "quickly confirm that address is correct before we proceed."
                ),
                guava.Field(
                    key="debit_card_delivery_address_confirmed",
                    description=(
                        "Read back the address on file to the customer and ask them to confirm it "
                        "is correct for debit card delivery. Record 'confirmed' if they verify the "
                        "address is correct, or record the corrected address they provide."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="security_question_set",
                    description=(
                        "Ask the customer if they would like to set up a security question for "
                        "their online banking profile now, or if they prefer to do this later "
                        "through the mobile app. Record 'set_during_call' if a security question "
                        "was established, 'deferred' if they chose to do it later, or leave blank "
                        "if the topic was not addressed."
                    ),
                    field_type="text",
                    required=False,
                ),
            ],
            on_complete=self.save_results,
        )

    def save_results(self):
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "contact_name": self.contact_name,
            "account_type": self.account_type,
            "disclosures_acknowledged": self.get_field("disclosures_acknowledged"),
            "paperless_statements_opted_in": self.get_field("paperless_statements_opted_in"),
            "overdraft_protection_opted_in": self.get_field("overdraft_protection_opted_in"),
            "debit_card_delivery_address_confirmed": self.get_field(
                "debit_card_delivery_address_confirmed"
            ),
            "security_question_set": self.get_field("security_question_set"),
        }
        print(json.dumps(results, indent=2))
        self.hangup(
            final_instructions=(
                f"Congratulate {self.contact_name} on completing their account setup. Provide a "
                f"brief summary of their selections: disclosures acknowledged, paperless statement "
                f"preference, overdraft protection choice, and debit card delivery address. Let "
                f"them know their debit card will arrive within 5 to 7 business days and that they "
                f"can begin using online and mobile banking immediately. Share the customer service "
                f"number for any questions and close the call warmly, welcoming them to First "
                f"National Bank."
            )
        )

    def recipient_unavailable(self):
        self.hangup(
            final_instructions=(
                f"You were unable to reach {self.contact_name}. Leave a warm, welcoming voicemail "
                f"identifying yourself as Jamie from First National Bank. Congratulate them on "
                f"opening their new {self.account_type} and let them know you were calling to help "
                f"complete their account setup. Ask them to call back at their convenience or visit "
                f"the bank's website to complete the setup steps online."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="New customer onboarding call for account setup and disclosures."
    )
    parser.add_argument("phone", help="The phone number to call (E.164 format, e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Full name of the new customer")
    parser.add_argument(
        "--account-type",
        default="checking account",
        help="Type of account being opened (default: 'checking account')",
    )
    args = parser.parse_args()

    controller = CustomerOnboardingController(
        contact_name=args.name,
        account_type=args.account_type,
    )

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=controller,
    )
