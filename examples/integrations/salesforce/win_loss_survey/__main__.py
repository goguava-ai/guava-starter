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


def get_opportunity(opp_id: str) -> dict | None:
    resp = requests.get(
        f"{API_BASE}/sobjects/Opportunity/{opp_id}",
        headers=SF_HEADERS,
        params={"fields": "Id,Name,Amount,StageName,CloseDate,AccountId"},
        timeout=10,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def log_note_on_opportunity(opp_id: str, body: str) -> None:
    """Creates a Note associated with the Opportunity via the ContentNote or classic Note API."""
    payload = {
        "ParentId": opp_id,
        "Title": f"Win/Loss Survey — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
        "Body": body,
        "IsPrivate": False,
    }
    resp = requests.post(
        f"{API_BASE}/sobjects/Note",
        headers=SF_HEADERS,
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()


def update_opportunity_loss_reason(opp_id: str, reason: str) -> None:
    """Updates the Loss_Reason__c custom field on the Opportunity."""
    resp = requests.patch(
        f"{API_BASE}/sobjects/Opportunity/{opp_id}",
        headers=SF_HEADERS,
        json={"Loss_Reason__c": reason},
        timeout=10,
    )
    resp.raise_for_status()


def log_task(what_id: str, subject: str, description: str) -> None:
    payload = {
        "WhatId": what_id,
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


agent = guava.Agent(
    name="Jordan",
    organization="Northgate Solutions",
    purpose=(
        "to gather candid win/loss feedback from prospects or customers after a deal "
        "closes — helping Northgate Solutions improve its sales process and product"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    opp_id = call.get_variable("opp_id")
    deal_outcome = call.get_variable("deal_outcome").lower()  # "won" or "lost"

    opp_name = "our recent proposal"
    opp_amount = ""

    try:
        opp = get_opportunity(opp_id)
        if opp:
            opp_name = opp.get("Name") or "our recent proposal"
            amount = opp.get("Amount")
            opp_amount = f"${amount:,.0f}" if amount else ""
    except Exception as e:
        logging.error("Failed to fetch Opportunity %s pre-call: %s", opp_id, e)

    call.set_variable("opp_name", opp_name)
    call.set_variable("opp_amount", opp_amount)
    call.reach_person(contact_full_name=contact_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    contact_name = call.get_variable("contact_name")
    opp_id = call.get_variable("opp_id")

    if outcome == "unavailable":
        logging.info("Unable to reach %s for win/loss survey on opp %s.", contact_name, opp_id)
        try:
            log_task(
                opp_id,
                subject="Win/Loss Survey — contact unavailable",
                description=(
                    f"Win/loss survey attempted — {contact_name} unavailable.\n"
                    f"Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
                ),
            )
        except Exception as e:
            logging.error("Failed to log missed-call Task: %s", e)

        call.hangup(
            final_instructions=(
                f"Leave a brief, warm voicemail for {contact_name} from Northgate Solutions. "
                "Let them know you're calling to gather some quick feedback and will try again. "
                "Keep it light and non-pressuring."
            )
        )
    elif outcome == "available":
        deal_outcome = call.get_variable("deal_outcome") or ""
        opp_name = call.get_variable("opp_name") or "our recent proposal"
        if deal_outcome == "won":
            opening = (
                f"Hi {contact_name}, this is Jordan from Northgate Solutions. "
                f"We're thrilled you chose us for {opp_name}, and I'm calling to ask a "
                "few quick questions about what made you decide to move forward with us."
            )
        else:
            opening = (
                f"Hi {contact_name}, this is Jordan from Northgate Solutions. "
                f"I know you went in a different direction on {opp_name}, and I truly "
                "appreciate you taking a moment to share some honest feedback — it helps us improve."
            )

        call.set_task(
            "record_feedback",
            objective=(
                f"Conduct a brief win/loss survey with {contact_name} about the "
                f"{'won' if deal_outcome == 'won' else 'lost'} deal '{opp_name}'. "
                "Ask thoughtful questions and capture candid, detailed responses."
            ),
            checklist=[
                guava.Say(opening),
                guava.Field(
                    key="primary_decision_factor",
                    field_type="multiple_choice",
                    description=(
                        "Ask: 'What was the single most important factor in your decision?' "
                        "Map their answer to the closest choice."
                    ),
                    choices=[
                        "price / cost",
                        "product features",
                        "ease of use / implementation",
                        "vendor reputation / trust",
                        "support and service",
                        "existing relationship with competitor",
                        "internal budget changes",
                        "other",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="competitor_chosen",
                    field_type="text",
                    description=(
                        "If it was a lost deal, ask: 'Are you comfortable sharing which solution "
                        "you went with?' Skip this question for won deals."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="our_strengths",
                    field_type="text",
                    description=(
                        "Ask: 'What did you feel we did well throughout the process?' "
                        "Capture their answer in detail."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="improvement_areas",
                    field_type="text",
                    description=(
                        "Ask: 'Is there anything we could have done better or differently?' "
                        "Encourage candid feedback. Capture their full response."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="would_consider_future",
                    field_type="multiple_choice",
                    description=(
                        "For lost deals: 'Would you consider us again in the future?' "
                        "For won deals: 'How likely are you to recommend us to a peer?' "
                        "Map to the appropriate choice."
                    ),
                    choices=["very likely", "likely", "unsure", "unlikely"],
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("record_feedback")
def on_done(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    opp_id = call.get_variable("opp_id")

    decision_factor = call.get_field("primary_decision_factor") or ""
    competitor = call.get_field("competitor_chosen") or ""
    strengths = call.get_field("our_strengths") or ""
    improvements = call.get_field("improvement_areas") or ""
    future = call.get_field("would_consider_future") or ""

    deal_outcome = call.get_variable("deal_outcome") or ""
    opp_name = call.get_variable("opp_name") or "our recent proposal"

    note_lines = [
        f"Win/Loss Survey — {deal_outcome.title()} — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
        f"Contact: {contact_name}",
        f"Opportunity: {opp_name}",
        f"Primary decision factor: {decision_factor}",
        f"Our strengths: {strengths}",
        f"Improvement areas: {improvements}",
        f"Would consider in future / recommend: {future}",
    ]
    if competitor:
        note_lines.append(f"Competitor chosen: {competitor}")

    logging.info(
        "Win/loss survey complete for opp %s — outcome: %s, factor: %s",
        opp_id, deal_outcome, decision_factor,
    )

    try:
        log_note_on_opportunity(opp_id, "\n".join(note_lines))
        logging.info("Note logged on opportunity %s.", opp_id)
    except Exception as e:
        logging.error("Failed to log Note: %s", e)

    if deal_outcome == "lost" and decision_factor:
        try:
            update_opportunity_loss_reason(opp_id, decision_factor)
            logging.info("Updated Loss_Reason__c on opp %s.", opp_id)
        except Exception as e:
            logging.warning("Could not update Loss_Reason__c (field may not exist): %s", e)

    try:
        log_task(
            opp_id,
            subject=f"Win/Loss Survey — {deal_outcome.title()}",
            description=f"Survey completed with {contact_name}.",
        )
    except Exception as e:
        logging.error("Failed to log Task: %s", e)

    call.hangup(
        final_instructions=(
            f"Thank {contact_name} sincerely for their time and candid feedback. "
            "Let them know the input is genuinely valuable and will be shared with the product "
            "and sales leadership team. "
            + ("Wish them great success with their chosen solution." if deal_outcome == "lost"
               else "Express excitement about working together and wish them a great day.")
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound win/loss survey call for a closed Salesforce Opportunity."
    )
    parser.add_argument("phone", help="Contact's phone number (E.164, e.g. +15551234567)")
    parser.add_argument("--opportunity-id", required=True, help="Salesforce Opportunity ID")
    parser.add_argument("--name", required=True, help="Full name of the contact")
    parser.add_argument(
        "--outcome",
        required=True,
        choices=["won", "lost"],
        help="Whether the deal was won or lost",
    )
    args = parser.parse_args()

    logging.info(
        "Initiating win/loss survey call to %s (%s) for opp %s — outcome: %s",
        args.name, args.phone, args.opportunity_id, args.outcome,
    )

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "opp_id": args.opportunity_id,
            "contact_name": args.name,
            "deal_outcome": args.outcome,
        },
    )
