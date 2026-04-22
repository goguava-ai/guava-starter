import guava
import os
import logging
from guava import logging_utils
from datetime import datetime, timezone
from pymongo import MongoClient


_client = MongoClient(os.environ["MONGODB_URI"])
_db = _client[os.environ["MONGODB_DATABASE"]]
leads = _db["leads"]


def save_lead(doc: dict) -> str:
    """Inserts a lead document and returns the inserted ID as a string."""
    doc["created_at"] = datetime.now(tz=timezone.utc)
    doc["source"] = "inbound_voice"
    result = leads.insert_one(doc)
    return str(result.inserted_id)


agent = guava.Agent(
    name="Riley",
    organization="Vantage",
    purpose=(
        "to help new prospects get connected with the Vantage sales team "
        "by collecting their information and understanding their needs"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "lead_capture",
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
    )


@agent.on_task_complete("lead_capture")
def on_lead_capture_done(call: guava.Call) -> None:
    name = call.get_field("full_name") or "Unknown"
    email = call.get_field("email") or ""
    company = call.get_field("company") or ""
    company_size = call.get_field("company_size") or ""
    use_case = call.get_field("use_case") or ""
    timeline = call.get_field("timeline") or ""

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
        call.hangup(
            final_instructions=(
                f"Thank {name} warmly for calling. Let them know their information "
                "has been recorded and a member of the Vantage team will be in touch "
                "within one business day. If they mentioned a specific timeline, "
                "acknowledge it. Wish them a great day."
            )
        )
    except Exception as e:
        logging.error("Failed to save lead for %s: %s", name, e)
        call.hangup(
            final_instructions=(
                f"Apologize to {name} for a brief technical issue. Let them know their "
                "information has been noted and someone will follow up within one business day. "
                "Thank them for their patience."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
