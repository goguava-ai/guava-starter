import guava
import os
import logging
import requests
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)

ZAPIER_WEBHOOK_URL = os.environ["ZAPIER_WEBHOOK_URL"]


def trigger_zap(payload: dict) -> None:
    resp = requests.post(ZAPIER_WEBHOOK_URL, json=payload, timeout=10)
    resp.raise_for_status()


# Score thresholds for routing decisions
TIER_MAP = {
    ("over $100k", "immediately"): "enterprise",
    ("over $100k", "1-3 months"): "enterprise",
    ("$25k-$100k", "immediately"): "mid_market",
    ("$25k-$100k", "1-3 months"): "mid_market",
    ("$25k-$100k", "3-6 months"): "mid_market",
}


def determine_tier(budget: str, timeline: str) -> str:
    return TIER_MAP.get((budget, timeline), "smb")


class LeadRoutingController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Nexus Technologies",
            agent_name="Jordan",
            agent_purpose=(
                "to qualify inbound sales leads for Nexus Technologies and route them to "
                "the right sales team based on their budget and timeline"
            ),
        )

        self.set_task(
            objective=(
                "A prospect is calling Nexus Technologies. Qualify the lead by collecting "
                "their contact information, understanding their use case, and capturing "
                "their budget and timeline so they can be routed to the right sales team."
            ),
            checklist=[
                guava.Say(
                    "Thanks for calling Nexus Technologies! I'm Jordan. "
                    "I'd love to learn a bit about what brings you in and make sure we "
                    "connect you with the right person on our team."
                ),
                guava.Field(
                    key="first_name",
                    field_type="text",
                    description="Ask for their first name.",
                    required=True,
                ),
                guava.Field(
                    key="last_name",
                    field_type="text",
                    description="Ask for their last name.",
                    required=True,
                ),
                guava.Field(
                    key="company",
                    field_type="text",
                    description="Ask what company they're with.",
                    required=True,
                ),
                guava.Field(
                    key="email",
                    field_type="text",
                    description="Ask for their business email address.",
                    required=True,
                ),
                guava.Field(
                    key="use_case",
                    field_type="text",
                    description=(
                        "Ask what problem they're trying to solve or what brought them "
                        "to Nexus Technologies. Capture a clear summary."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="budget",
                    field_type="multiple_choice",
                    description=(
                        "Ask if they have a rough budget in mind. Frame it naturally: "
                        "'Just to help connect you with the right team, do you have a "
                        "rough investment range in mind?'"
                    ),
                    choices=["under $10k", "$10k-$25k", "$25k-$100k", "over $100k", "not sure yet"],
                    required=False,
                ),
                guava.Field(
                    key="timeline",
                    field_type="multiple_choice",
                    description="Ask when they're hoping to move forward.",
                    choices=["immediately", "1-3 months", "3-6 months", "just exploring"],
                    required=False,
                ),
                guava.Field(
                    key="num_employees",
                    field_type="multiple_choice",
                    description="Ask roughly how many employees their company has.",
                    choices=["1-50", "51-200", "201-1000", "1001-5000", "over 5000"],
                    required=False,
                ),
            ],
            on_complete=self.route_lead,
        )

        self.accept_call()

    def route_lead(self):
        first = self.get_field("first_name") or ""
        last = self.get_field("last_name") or ""
        company = self.get_field("company") or ""
        email = self.get_field("email") or ""
        use_case = self.get_field("use_case") or ""
        budget = self.get_field("budget") or "not sure yet"
        timeline = self.get_field("timeline") or "just exploring"
        employees = self.get_field("num_employees") or ""

        tier = determine_tier(budget, timeline)

        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "first_name": first,
            "last_name": last,
            "company": company,
            "email": email,
            "use_case": use_case,
            "budget": budget,
            "timeline": timeline,
            "num_employees": employees,
            "routing_tier": tier,
            "source": "guava_inbound_call",
        }

        logging.info(
            "Routing lead %s %s (%s) — tier: %s", first, last, email, tier,
        )

        try:
            trigger_zap(payload)
            logging.info("Lead routing Zap triggered for %s %s.", first, last)
            tier_message = {
                "enterprise": "one of our enterprise account executives",
                "mid_market": "one of our mid-market sales specialists",
                "smb": "a member of our sales team",
            }.get(tier, "the right person on our team")

            self.hangup(
                final_instructions=(
                    f"Thank {first} for their time. Let them know their information has been "
                    f"passed along to {tier_message} who will be in touch within one business day. "
                    "If they have an immediate question, suggest they email sales@nexustech.com. "
                    "Wish them a great day."
                )
            )
        except Exception as e:
            logging.error("Failed to trigger lead routing Zap: %s", e)
            self.hangup(
                final_instructions=(
                    f"Apologize to {first} for a brief technical issue. Let them know their "
                    "inquiry has been captured and someone will reach out to them at the email "
                    "they provided. Thank them for their patience."
                )
            )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=LeadRoutingController,
    )
