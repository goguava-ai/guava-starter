import guava
import os
import logging
from guava import logging_utils
import json
import argparse
from datetime import datetime, timezone



class LoyaltyEnrollmentController(guava.CallController):
    def __init__(self, contact_name, order_number):
        super().__init__()
        self.contact_name = contact_name
        self.order_number = order_number
        self.set_persona(
            organization_name="ShopNow",
            agent_name="Morgan",
            agent_purpose=(
                "to welcome first-time buyers to ShopNow, explain the loyalty rewards program benefits, "
                "and collect their opt-in confirmation and communication preferences"
            ),
        )
        self.reach_person(
            contact_full_name=self.contact_name,
            on_success=self.begin_loyalty_enrollment,
            on_failure=self.recipient_unavailable,
        )

    def begin_loyalty_enrollment(self):
        self.set_task(
            objective=(
                f"Welcome {self.contact_name} as a first-time ShopNow customer following their order "
                f"#{self.order_number}. Introduce the ShopNow Rewards loyalty program, explain the key "
                "benefits (points on every purchase, exclusive member discounts, birthday rewards, "
                "and early access to sales), and ask if they would like to enroll. "
                "If they enroll, collect their preferred communication channel for rewards updates, "
                "optionally gather their birthday month and day for a birthday bonus, "
                "and ask if they have a friend's email to share for a referral reward. "
                "Keep the tone warm, welcoming, and benefit-focused."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.contact_name}, this is Morgan calling from ShopNow. "
                    f"Welcome — we're so excited to have you as a new customer! "
                    f"Your order #{self.order_number} is on its way, and I wanted to take a moment "
                    "to personally introduce you to our ShopNow Rewards program. "
                    "As a member, you earn points on every purchase, get access to exclusive discounts, "
                    "receive a special birthday reward, and enjoy early access to our biggest sales. "
                    "Best of all, enrollment is completely free."
                ),
                guava.Field(
                    key="loyalty_enrollment_accepted",
                    description=(
                        "Whether the customer agreed to enroll in the ShopNow Rewards loyalty program: "
                        "'yes', 'no', or a description of their response"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Say(
                    "Fantastic! To make sure you never miss out on your rewards and exclusive offers, "
                    "how would you prefer we send you updates — by email, text message, or both?"
                ),
                guava.Field(
                    key="preferred_communication_channel",
                    description=(
                        "The customer's preferred channel for receiving loyalty rewards updates and offers: "
                        "'email', 'sms', or 'both'"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="birthday_for_rewards",
                    description=(
                        "The customer's birthday month and day for their annual birthday reward. "
                        "Capture in a recognizable date or month-day format. "
                        "Leave blank if they prefer not to share."
                    ),
                    field_type="date",
                    required=False,
                ),
                guava.Field(
                    key="referral_email_to_share",
                    description=(
                        "An email address of a friend or family member the customer would like to refer to ShopNow "
                        "in exchange for a referral bonus. Leave blank if they do not wish to refer anyone."
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
            "order_number": self.order_number,
            "loyalty_enrollment_accepted": self.get_field("loyalty_enrollment_accepted"),
            "preferred_communication_channel": self.get_field("preferred_communication_channel"),
            "birthday_for_rewards": self.get_field("birthday_for_rewards"),
            "referral_email_to_share": self.get_field("referral_email_to_share"),
        }
        print(json.dumps(results, indent=2))
        logging.info(
            "Loyalty enrollment call completed for %s, order %s", self.contact_name, self.order_number
        )
        self.hangup(
            final_instructions=(
                "Thank the customer for joining ShopNow Rewards and for their first purchase. "
                "Let them know they will receive a confirmation of their enrollment via their chosen "
                "communication channel shortly. "
                "If they declined enrollment, thank them for their time and let them know the offer "
                "remains open whenever they are ready. "
                "Wish them a wonderful day and close the call warmly."
            )
        )

    def recipient_unavailable(self):
        logging.warning(
            "Could not reach %s for loyalty enrollment outreach on order %s.",
            self.contact_name,
            self.order_number,
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(description="ShopNow loyalty program enrollment agent")
    parser.add_argument("phone", help="Customer phone number to call")
    parser.add_argument("--name", required=True, help="Customer full name")
    parser.add_argument("--order-number", required=True, help="Customer's first order number")
    args = parser.parse_args()

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=LoyaltyEnrollmentController(
            contact_name=args.name,
            order_number=args.order_number,
        ),
    )
