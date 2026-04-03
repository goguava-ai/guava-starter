import guava
import os
import logging
from datetime import datetime, timezone
from pymongo import MongoClient

logging.basicConfig(level=logging.INFO)

_client = MongoClient(os.environ["MONGODB_URI"])
_db = _client[os.environ["MONGODB_DATABASE"]]
leads = _db["leads"]


def save_lead(doc: dict) -> str:
    """Inserts a lead document and returns the inserted ID as a string."""
    doc["created_at"] = datetime.now(tz=timezone.utc)
    doc["source"] = "inbound_voice"
    result = leads.insert_one(doc)
    return str(result.inserted_id)


class LeadCaptureController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Vantage",
            agent_name="Riley",
            agent_purpose=(
                "to help new prospects get connected with the Vantage sales team "
                "by collecting their information and understanding their needs"
            ),
        )

        self.set_task(
            objective=(
                "A new prospect has called Vantage. Greet them, collect their contact "
                "information and understand their use case, then save a lead record."
            ),
            checklist=[
                guava.Say(
                    "Thanks for calling Vantage. I'm Riley. "
                    "I'd love to learn about what brought you to us today "
                    "and make sure the right team follows up with you."
                ),
                guava.Field(
                    key="full_name",
                    field_type="text",
                    description="Ask for their full name.",
                    required=True,
                ),
                guava.Field(
                    key="email",
                    field_type="text",
                    description="Ask for their business email address.",
                    required=True,
                ),
                guava.Field(
                    key="company",
                    field_type="text",
                    description="Ask what company they're with.",
                    required=True,
                ),
                guava.Field(
                    key="company_size",
                    field_type="multiple_choice",
                    description="Ask roughly how large their company is.",
                    choices=["1–10", "11–50", "51–200", "201–1000", "1000+"],
                    required=False,
                ),
                guava.Field(
                    key="use_case",
                    field_type="text",
                    description=(
                        "Ask what they're hoping Vantage can help them with. "
                        "Capture their answer in their own words."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="timeline",
                    field_type="multiple_choice",
                    description="Ask when they're hoping to get something in place.",
                    choices=["immediately", "1–3 months", "3–6 months", "just exploring"],
                    required=False,
                ),
            ],
            on_complete=self.save_lead,
        )

        self.accept_call()

    def save_lead(self):
        name = self.get_field("full_name") or "Unknown"
        email = self.get_field("email") or ""
        company = self.get_field("company") or ""
        company_size = self.get_field("company_size") or ""
        use_case = self.get_field("use_case") or ""
        timeline = self.get_field("timeline") or ""

        lead_doc = {
            "name": name,
            "email": email,
            "company": company,
            "company_size": company_size,
            "use_case": use_case,
            "timeline": timeline,
            "status": "new",
        }

        logging.info("Saving lead for %s (%s) at %s", name, email, company)

        try:
            lead_id = save_lead(lead_doc)
            logging.info("Lead saved with ID: %s", lead_id)
            self.hangup(
                final_instructions=(
                    f"Thank {name} warmly for calling. Let them know their information "
                    "has been recorded and a member of the Vantage team will be in touch "
                    "within one business day. If they mentioned a specific timeline, "
                    "acknowledge it. Wish them a great day."
                )
            )
        except Exception as e:
            logging.error("Failed to save lead for %s: %s", name, e)
            self.hangup(
                final_instructions=(
                    f"Apologize to {name} for a brief technical issue. Let them know their "
                    "information has been noted and someone will follow up within one business day. "
                    "Thank them for their patience."
                )
            )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=LeadCaptureController,
    )
