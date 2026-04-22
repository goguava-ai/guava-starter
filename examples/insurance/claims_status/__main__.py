import guava
import os
import logging
from guava import logging_utils
import json
import argparse
from datetime import datetime, timezone



class ClaimsStatusController(guava.CallController):
    def __init__(self, contact_name: str, claim_number: str, status: str):
        super().__init__()
        self.contact_name = contact_name
        self.claim_number = claim_number
        self.status = status

        self.set_persona(
            organization_name="Keystone Property & Casualty - Claims",
            agent_name="Morgan",
            agent_purpose=(
                "to provide claimants with a proactive status update on their open claim "
                "and gather any outstanding information needed to keep the claim moving forward"
            ),
        )
        self.reach_person(
            contact_full_name=self.contact_name,
            on_success=self.start_status_flow,
            on_failure=self.recipient_unavailable,
        )

    def start_status_flow(self):
        self.set_task(
            objective=(
                f"You are calling {self.contact_name} with a status update on claim number "
                f"{self.claim_number}. The current status is: {self.status}. "
                "Clearly communicate this status and explain what the next steps are. "
                "Ask whether the claimant has a preferred repair vendor, whether they have "
                "any additional documentation to submit, and whether they need a follow-up "
                "from an adjuster. Be empathetic, clear, and professional. Avoid making any "
                "promises about settlement amounts or timelines outside of what is stated."
            ),
            checklist=[
                guava.Say(
                    f"Hello {self.contact_name}, this is Morgan calling from the Claims "
                    f"department at Keystone Property & Casualty. I'm calling with an update "
                    f"on your claim number {self.claim_number}. I have a few quick questions "
                    "for you as well to help us keep things moving."
                ),
                guava.Field(
                    key="update_understood",
                    description=(
                        "Confirmation that the claimant understood the status update provided, "
                        "and any immediate questions or concerns they raised"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="repair_vendor_preference",
                    description=(
                        "Whether the claimant has a preferred repair contractor or vendor "
                        "they would like to use, and the vendor name if provided"
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="additional_documentation_available",
                    description=(
                        "Whether the claimant has additional documentation, photos, receipts, "
                        "or estimates available to submit to support the claim"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="follow_up_needed",
                    description=(
                        "Whether the claimant is requesting a follow-up call from a licensed "
                        "adjuster, and the reason or urgency if applicable"
                    ),
                    field_type="text",
                    required=True,
                ),
            ],
            on_complete=self.save_results,
        )

    def save_results(self):
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "use_case": "claims_status_update",
            "contact_name": self.contact_name,
            "claim_number": self.claim_number,
            "status_communicated": self.status,
            "update_understood": self.get_field("update_understood"),
            "repair_vendor_preference": self.get_field("repair_vendor_preference"),
            "additional_documentation_available": self.get_field(
                "additional_documentation_available"
            ),
            "follow_up_needed": self.get_field("follow_up_needed"),
        }
        print(json.dumps(results, indent=2))
        logging.info("Claims status results saved: %s", results)
        self.hangup(
            final_instructions=(
                "Thank you for your time today. We have noted your responses and will make "
                "sure your claim file is updated accordingly. If you submitted or plan to "
                "submit additional documentation, please send it to the email or portal link "
                "in your original claim confirmation. If you requested adjuster follow-up, "
                "someone will be in touch within one business day. We appreciate your patience "
                "and are committed to resolving your claim as quickly as possible. Take care."
            )
        )

    def recipient_unavailable(self):
        logging.warning(
            "Could not reach %s for claims status update on claim %s.",
            self.contact_name,
            self.claim_number,
        )
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "use_case": "claims_status_update",
            "contact_name": self.contact_name,
            "claim_number": self.claim_number,
            "outcome": "recipient_unavailable",
        }
        print(json.dumps(results, indent=2))
        self.hangup(
            final_instructions=(
                "We were unable to reach the claimant. "
                "Please attempt re-contact or send a written status update via email."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound claims status update call for Keystone Property & Casualty"
    )
    parser.add_argument("phone", help="Phone number to dial")
    parser.add_argument("--name", required=True, help="Full name of the claimant")
    parser.add_argument("--claim-number", required=True, help="Claim number")
    parser.add_argument(
        "--status",
        default="under review",
        help="Current claim status description (default: 'under review')",
    )
    args = parser.parse_args()

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=ClaimsStatusController(
            contact_name=args.name,
            claim_number=args.claim_number,
            status=args.status,
        ),
    )
