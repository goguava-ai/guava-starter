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

INTENT_TO_STAGE = {
    "renew as-is": "Proposal/Price Quote",
    "renew with changes": "Value Proposition",
    "need more time": "Perception Analysis",
    "not renewing": "Closed Lost",
}


def get_opportunity(opp_id: str) -> dict | None:
    resp = requests.get(
        f"{API_BASE}/sobjects/Opportunity/{opp_id}",
        headers=SF_HEADERS,
        params={"fields": "Id,Name,Amount,CloseDate,StageName,AccountId"},
        timeout=10,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def update_opportunity(opp_id: str, updates: dict) -> None:
    resp = requests.patch(
        f"{API_BASE}/sobjects/Opportunity/{opp_id}",
        headers=SF_HEADERS,
        json=updates,
        timeout=10,
    )
    resp.raise_for_status()


def log_task(what_id: str, subject: str, description: str) -> None:
    payload = {
        "WhatId": what_id,
        "Subject": subject,
        "Description": description,
        "Status": "Completed",
        "Priority": "High",
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


agent = guava.Agent(
    name="Morgan",
    organization="Veritas Software",
    purpose=(
        "to connect with customers ahead of their contract renewal, understand their "
        "intentions, and make sure the renewal process goes smoothly"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    opp_id = call.get_variable("opp_id")

    opp_name = "your renewal"
    opp_amount = ""
    close_date = ""

    try:
        opp = get_opportunity(opp_id)
        if opp:
            opp_name = opp.get("Name") or "your renewal"
            amount = opp.get("Amount")
            opp_amount = f"${amount:,.0f}" if amount else ""
            close_date_raw = opp.get("CloseDate")
            if close_date_raw:
                dt = datetime.strptime(close_date_raw, "%Y-%m-%d")
                close_date = dt.strftime("%B %d, %Y")
    except Exception as e:
        logging.error("Failed to fetch Opportunity %s pre-call: %s", opp_id, e)

    call.set_variable("opp_name", opp_name)
    call.set_variable("opp_amount", opp_amount)
    call.set_variable("close_date", close_date)
    call.reach_person(contact_full_name=contact_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    contact_name = call.get_variable("contact_name")
    opp_id = call.get_variable("opp_id")

    if outcome == "unavailable":
        logging.info(
            "Unable to reach %s for contract renewal call on opp %s.",
            contact_name, opp_id,
        )
        try:
            log_task(
                opp_id,
                subject="Contract renewal call — contact unavailable",
                description=(
                    f"Renewal outreach attempted — {contact_name} unavailable, voicemail left.\n"
                    f"Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
                ),
            )
        except Exception as e:
            logging.error("Failed to log missed-call Task for opp %s: %s", opp_id, e)

        opp_name = call.get_variable("opp_name") or "your renewal"
        call.hangup(
            final_instructions=(
                f"Leave a professional voicemail for {contact_name} from Veritas Software. "
                f"Mention you're calling about their upcoming contract renewal for {opp_name} "
                "and that you'd love to connect. Ask them to call back or watch for an email. "
                "Keep it brief and warm."
            )
        )
    elif outcome == "available":
        opp_name = call.get_variable("opp_name") or "your renewal"
        opp_amount = call.get_variable("opp_amount") or ""
        close_date = call.get_variable("close_date") or ""
        amount_note = f" valued at {opp_amount}" if opp_amount else ""
        date_note = f" expiring on {close_date}" if close_date else " coming up for renewal"

        call.set_task(
            "record_outcome",
            objective=(
                f"Speak with {contact_name} about renewing '{opp_name}'"
                f"{amount_note}{date_note}. Understand their renewal intent and any requested changes."
            ),
            checklist=[
                guava.Say(
                    f"Hi {contact_name}, this is Morgan from Veritas Software. "
                    f"I'm calling because your contract{date_note} and I wanted to "
                    "connect personally to make the renewal as smooth as possible for you."
                ),
                guava.Field(
                    key="renewal_intent",
                    field_type="multiple_choice",
                    description=(
                        "Ask what they're planning to do at renewal. "
                        "'What are you thinking in terms of the renewal?'"
                    ),
                    choices=["renew as-is", "renew with changes", "need more time", "not renewing"],
                    required=True,
                ),
                guava.Field(
                    key="requested_changes",
                    field_type="text",
                    description=(
                        "If they want to renew with changes, ask what changes they have in mind — "
                        "scope, pricing, terms, or features. Skip if renewing as-is or not renewing."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="cancellation_reason",
                    field_type="text",
                    description=(
                        "If they are not renewing, ask if they're comfortable sharing the reason. "
                        "Capture their full response without pushing back."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="preferred_followup",
                    field_type="multiple_choice",
                    description="Ask how they'd prefer to receive renewal paperwork or next steps.",
                    choices=["email", "phone call", "both"],
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("record_outcome")
def on_done(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    opp_id = call.get_variable("opp_id")

    intent = call.get_field("renewal_intent") or "need more time"
    changes = call.get_field("requested_changes") or ""
    reason = call.get_field("cancellation_reason") or ""
    followup = call.get_field("preferred_followup") or "email"

    new_stage = INTENT_TO_STAGE.get(intent, "Perception Analysis")

    description_lines = [
        f"Contract renewal call — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
        f"Contact: {contact_name}",
        f"Intent: {intent}",
        f"Preferred follow-up: {followup}",
    ]
    if changes:
        description_lines.append(f"Requested changes: {changes}")
    if reason:
        description_lines.append(f"Cancellation reason: {reason}")

    logging.info(
        "Renewal call complete for opp %s — intent: %s, new stage: %s",
        opp_id, intent, new_stage,
    )

    try:
        update_opportunity(opp_id, {"StageName": new_stage})
        logging.info("Opportunity %s updated to stage: %s", opp_id, new_stage)
        log_task(
            opp_id,
            subject=f"Contract renewal call — {intent}",
            description="\n".join(description_lines),
        )
        logging.info("Task logged for opportunity %s.", opp_id)
    except Exception as e:
        logging.error("Failed to update Salesforce for opp %s: %s", opp_id, e)

    if intent == "not renewing":
        call.hangup(
            final_instructions=(
                f"Thank {contact_name} sincerely for their past partnership. "
                "Express that we're sorry to see them go and that their feedback has been "
                "shared with the team. If they're open to it, let them know they're always "
                "welcome back. Wish them well."
            )
        )
    elif intent == "renew with changes":
        call.hangup(
            final_instructions=(
                f"Thank {contact_name} for their continued partnership. "
                "Let them know the requested changes have been noted and an account executive "
                "will send an updated proposal within two business days. "
                "Confirm they'll receive it via their preferred method. Wish them a great day."
            )
        )
    else:
        email_note = "We'll send renewal paperwork via email. " if followup in ("email", "both") else ""
        call_note = "Someone will call to walk through it. " if followup in ("phone call", "both") else ""
        call.hangup(
            final_instructions=(
                f"Thank {contact_name} and confirm the next steps. "
                + email_note + call_note
                + "Let them know they're in good hands and wish them a great day."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound contract renewal call for a Salesforce Opportunity."
    )
    parser.add_argument("phone", help="Contact's phone number (E.164, e.g. +15551234567)")
    parser.add_argument("--opportunity-id", required=True, help="Salesforce Opportunity ID")
    parser.add_argument("--name", required=True, help="Full name of the contact to reach")
    args = parser.parse_args()

    logging.info(
        "Initiating contract renewal call to %s (%s) for opportunity %s",
        args.name, args.phone, args.opportunity_id,
    )

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "opp_id": args.opportunity_id,
            "contact_name": args.name,
        },
    )
