import logging
import os
from datetime import datetime, timezone

import guava
from google.cloud import bigquery
from guava import logging_utils

# Set this to your BigQuery table: "your_project.your_dataset.your_table"
BIGQUERY_TABLE = os.environ["BIGQUERY_TABLE"]


agent = guava.Agent(
    name="Casey",
    organization="Acme Corp",
    purpose=(
        "to learn about a prospective customer's needs "
        "and pass the right information to the sales team"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "save_to_bigquery",
        objective=(
            "A potential customer has called in. Qualify the lead by understanding "
            "their company, role, use case, team size, and buying timeline."
        ),
        checklist=[
            guava.Say(
                "Thanks for calling Acme Corp. I'm Casey. "
                "I'd love to learn a bit about what you're looking for "
                "so I can connect you with the right person on our team."
            ),
            guava.Field(
                key="contact_name",
                field_type="text",
                description="Ask for their full name.",
                required=True,
            ),
            guava.Field(
                key="contact_email",
                field_type="text",
                description="Ask for their email address so the team can follow up.",
                required=True,
            ),
            guava.Field(
                key="company_name",
                field_type="text",
                description="Ask what company they're with.",
                required=True,
            ),
            guava.Field(
                key="role",
                field_type="multiple_choice",
                description="Ask about their role at the company.",
                choices=[
                    "executive or founder",
                    "director or VP",
                    "manager",
                    "individual contributor",
                    "other",
                ],
                required=True,
            ),
            guava.Field(
                key="use_case",
                field_type="text",
                description="Ask what they're hoping to use Acme Corp for — what problem they're trying to solve.",
                required=True,
            ),
            guava.Field(
                key="team_size",
                field_type="multiple_choice",
                description="Ask approximately how many people would be using the product.",
                choices=["fewer than 10", "10–50", "51–200", "more than 200"],
                required=True,
            ),
            guava.Field(
                key="timeline",
                field_type="multiple_choice",
                description="Ask when they're looking to get started.",
                choices=[
                    "immediately",
                    "within the next 3 months",
                    "3–6 months from now",
                    "just researching for now",
                ],
                required=True,
            ),
            guava.Field(
                key="heard_from",
                field_type="multiple_choice",
                description="Ask how they heard about Acme Corp.",
                choices=["Google search", "referral", "social media", "event or webinar", "other"],
                required=False,
            ),
        ],
    )


@agent.on_task_complete("save_to_bigquery")
def on_done(call: guava.Call) -> None:
    row = {
        "call_timestamp": datetime.now(timezone.utc).isoformat(),
        "contact_name": call.get_field("contact_name"),
        "contact_email": call.get_field("contact_email"),
        "company_name": call.get_field("company_name"),
        "role": call.get_field("role"),
        "use_case": call.get_field("use_case"),
        "team_size": call.get_field("team_size"),
        "timeline": call.get_field("timeline"),
        "heard_from": call.get_field("heard_from"),
    }

    client = bigquery.Client()
    errors = client.insert_rows_json(BIGQUERY_TABLE, [row])
    if errors:
        logging.error("BigQuery insert failed: %s", errors)
    else:
        logging.info("Row written to BigQuery: %s", row)

    name = call.get_field("contact_name") or "there"
    timeline = call.get_field("timeline") or ""

    call.hangup(
        final_instructions=(
            f"Thank {name} for taking the time to share their details. "
            "Let them know someone from the sales team will reach out by email within one business day. "
            + (
                "Since they mentioned they need something immediately, let them know to expect a call today. "
                if "immediately" in timeline
                else ""
            )
            + "Wish them a great day."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
