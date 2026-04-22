import argparse
import logging
import os
from datetime import datetime, timezone

import guava
import requests
from guava import logging_utils

SALESFORCE_INSTANCE_URL = os.environ["SALESFORCE_INSTANCE_URL"]
SALESFORCE_ACCESS_TOKEN = os.environ["SALESFORCE_ACCESS_TOKEN"]
SF_HEADERS = {
    "Authorization": f"Bearer {SALESFORCE_ACCESS_TOKEN}",
    "Content-Type": "application/json",
}
API_BASE = f"{SALESFORCE_INSTANCE_URL}/services/data/v66.0"


def find_contact_by_email(email: str) -> dict | None:
    q = f"SELECT Id, FirstName, AccountId FROM Contact WHERE Email = '{email}' LIMIT 1"
    resp = requests.get(
        f"{API_BASE}/query",
        headers=SF_HEADERS,
        params={"q": q},
        timeout=10,
    )
    resp.raise_for_status()
    records = resp.json().get("records", [])
    return records[0] if records else None


def create_nps_response(contact_id: str, account_id: str, score: int, category: str, verbatim: str) -> str:
    """Creates an NPS_Response__c custom object record. Returns the new record ID."""
    payload = {
        "Contact__c": contact_id,
        "Account__c": account_id,
        "NPS_Score__c": score,
        "NPS_Category__c": category,
        "Verbatim_Feedback__c": verbatim,
        "Survey_Date__c": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "Channel__c": "Phone",
    }
    resp = requests.post(
        f"{API_BASE}/sobjects/NPS_Response__c",
        headers=SF_HEADERS,
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("id", "")


def log_task(contact_id: str, account_id: str, subject: str, description: str) -> None:
    payload = {
        "WhoId": contact_id,
        "WhatId": account_id,
        "Subject": subject,
        "Description": description,
        "Status": "Completed",
        "Priority": "Normal",
        "Type": "Call",
        "TaskSubtype": "Call",
        "ActivityDate": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }
    resp = requests.post(
        f"{API_BASE}/sobjects/Task",
        headers=SF_HEADERS,
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()


def nps_category(score: int) -> str:
    if score >= 9:
        return "Promoter"
    if score >= 7:
        return "Passive"
    return "Detractor"


agent = guava.Agent(
    name="Sam",
    organization="Lumis Corp",
    purpose=(
        "to collect a brief Net Promoter Score survey from Lumis Corp customers "
        "and understand how we can improve their experience"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    call.reach_person(contact_full_name=contact_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    contact_name = call.get_variable("contact_name")

    if outcome == "unavailable":
        logging.info("Unable to reach %s for NPS survey.", contact_name)
        call.hangup(
            final_instructions=(
                f"Leave a brief, friendly voicemail for {contact_name} from Lumis Corp. "
                "Let them know you're calling to gather some quick feedback on their experience "
                "and will try again another time. No need to ask them to call back."
            )
        )
    elif outcome == "available":
        call.set_task(
            "record_response",
            objective=(
                f"Conduct a short NPS survey with {contact_name}. Keep it brief and respectful "
                "of their time — aim to complete the survey in under two minutes."
            ),
            checklist=[
                guava.Say(
                    f"Hi {contact_name}, this is Sam from Lumis Corp. I'm calling to ask "
                    "just a couple quick questions about your experience with us — it should only "
                    "take about a minute. Is now a good time?"
                ),
                guava.Field(
                    key="nps_score",
                    field_type="multiple_choice",
                    description=(
                        "Ask: 'On a scale from 0 to 10, how likely are you to recommend Lumis Corp "
                        "to a colleague or friend?' Capture their score. If they give a range, take "
                        "the midpoint."
                    ),
                    choices=["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"],
                    required=True,
                ),
                guava.Field(
                    key="nps_reason",
                    field_type="text",
                    description=(
                        "Ask: 'What's the main reason for that score?' "
                        "Let them share freely. Capture their full verbatim response."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="improvement_suggestion",
                    field_type="text",
                    description=(
                        "Ask: 'Is there anything specific we could do to improve your experience?' "
                        "Keep it optional — if they say nothing else comes to mind, that's fine."
                    ),
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("record_response")
def on_done(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    contact_email = call.get_variable("contact_email")

    score_str = call.get_field("nps_score") or "0"
    reason = call.get_field("nps_reason") or ""
    suggestion = call.get_field("improvement_suggestion") or ""

    try:
        score = int(score_str)
    except ValueError:
        score = 0

    category = nps_category(score)
    verbatim = reason
    if suggestion:
        verbatim += f"\n\nSuggestion: {suggestion}"

    logging.info(
        "NPS survey complete for %s — score: %d, category: %s",
        contact_name, score, category,
    )

    try:
        contact = find_contact_by_email(contact_email)
    except Exception as e:
        logging.error("Contact lookup failed for %s: %s", contact_email, e)
        contact = None

    if contact:
        contact_id = contact["Id"]
        account_id = contact.get("AccountId") or ""
        try:
            record_id = create_nps_response(contact_id, account_id, score, category, verbatim)
            logging.info("NPS_Response__c created: %s", record_id)
        except Exception as e:
            logging.error("Failed to create NPS_Response__c: %s", e)
        try:
            log_task(
                contact_id,
                account_id,
                subject=f"NPS Survey — Score {score} ({category})",
                description=(
                    f"NPS survey completed — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}\n"
                    f"Score: {score} ({category})\n"
                    f"Feedback: {verbatim}"
                ),
            )
            logging.info("Task logged for contact %s.", contact_id)
        except Exception as e:
            logging.error("Failed to log Task: %s", e)
    else:
        logging.warning("No Salesforce Contact found for email %s — skipping record creation.", contact_email)

    if score <= 6:
        call.hangup(
            final_instructions=(
                f"Thank {contact_name} sincerely for their honest feedback. "
                "Let them know their response has been shared with the team and that someone "
                "will be following up to better understand their experience. "
                "Do not be defensive — be genuinely appreciative."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {contact_name} warmly for the positive feedback and for their time. "
                "Let them know their input helps the team continue improving. "
                "Wish them a great day."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound NPS survey call for a Salesforce Contact."
    )
    parser.add_argument("phone", help="Contact's phone number (E.164, e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Full name of the contact")
    parser.add_argument("--email", required=True, help="Contact's email address (used to look up their Salesforce record)")
    args = parser.parse_args()

    logging.info("Initiating NPS survey call to %s (%s)", args.name, args.phone)

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "contact_name": args.name,
            "contact_email": args.email,
        },
    )
