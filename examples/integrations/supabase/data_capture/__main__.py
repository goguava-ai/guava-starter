import guava
import os
import logging
import requests
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
REST_URL = f"{SUPABASE_URL}/rest/v1"


def get_headers() -> dict:
    service_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def insert_lead(data: dict) -> dict | None:
    table = os.environ.get("SUPABASE_LEADS_TABLE", "leads")
    resp = requests.post(
        f"{REST_URL}/{table}",
        headers=get_headers(),
        json=data,
        timeout=10,
    )
    resp.raise_for_status()
    rows = resp.json()
    return rows[0] if rows else None


class DataCaptureController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Clearline",
            agent_name="Jamie",
            agent_purpose=(
                "to capture inbound lead information and log it to the Clearline database in Supabase"
            ),
        )

        self.set_task(
            objective=(
                "An inbound lead has called. Collect their contact information, company, interest area, "
                "and timeline, then save it to Supabase."
            ),
            checklist=[
                guava.Say(
                    "Thank you for calling Clearline. This is Jamie. "
                    "I'd love to learn a bit about you and how we can help."
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
                    description="Ask for their email address.",
                    required=True,
                ),
                guava.Field(
                    key="phone",
                    field_type="text",
                    description="Ask for the best phone number to reach them.",
                    required=False,
                ),
                guava.Field(
                    key="company",
                    field_type="text",
                    description="Ask what company they're with.",
                    required=False,
                ),
                guava.Field(
                    key="interest",
                    field_type="text",
                    description="Ask what brought them to Clearline and what they're looking for help with.",
                    required=True,
                ),
                guava.Field(
                    key="timeline",
                    field_type="multiple_choice",
                    description="Ask roughly when they're hoping to get started.",
                    choices=["immediately", "within a month", "within 3 months", "just exploring"],
                    required=True,
                ),
            ],
            on_complete=self.save_lead,
        )

        self.accept_call()

    def save_lead(self):
        full_name = self.get_field("full_name") or ""
        email = self.get_field("email") or ""
        phone = self.get_field("phone") or ""
        company = self.get_field("company") or ""
        interest = self.get_field("interest") or ""
        timeline = self.get_field("timeline") or ""

        data: dict = {
            "full_name": full_name,
            "email": email,
            "status": "new",
            "source": "inbound_phone",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if phone:
            data["phone"] = phone
        if company:
            data["company"] = company
        if interest:
            data["interest"] = interest
        if timeline:
            data["timeline"] = timeline

        logging.info("Saving lead to Supabase: %s (%s)", full_name, email)

        saved = None
        try:
            saved = insert_lead(data)
            logging.info("Lead saved: %s", saved.get("id") if saved else None)
        except Exception as e:
            logging.error("Failed to save lead: %s", e)

        first_name = full_name.split()[0] if full_name else "there"

        if saved:
            self.hangup(
                final_instructions=(
                    f"Thank {first_name} for reaching out to Clearline. "
                    "Let them know a member of our team will follow up within one business day. "
                    "Wish them a great day."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Thank {first_name} for their interest in Clearline. "
                    "Let them know we had a small technical issue but their inquiry has been noted "
                    "and someone will follow up soon. Wish them a great day."
                )
            )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=DataCaptureController,
    )
