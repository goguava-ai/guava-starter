import guava
import os
import logging
import argparse
import requests
from datetime import datetime

logging.basicConfig(level=logging.INFO)

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
        "ActivityDate": datetime.utcnow().strftime("%Y-%m-%d"),
    }
    resp = requests.post(
        f"{API_BASE}/sobjects/Task",
        headers=SF_HEADERS,
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()


class ContractRenewalController(guava.CallController):
    def __init__(self, opp_id: str, contact_name: str):
        super().__init__()
        self.opp_id = opp_id
        self.contact_name = contact_name
        self.opp_name = "your renewal"
        self.opp_amount = ""
        self.close_date = ""

        try:
            opp = get_opportunity(opp_id)
            if opp:
                self.opp_name = opp.get("Name") or "your renewal"
                amount = opp.get("Amount")
                self.opp_amount = f"${amount:,.0f}" if amount else ""
                close_date_raw = opp.get("CloseDate")
                if close_date_raw:
                    dt = datetime.strptime(close_date_raw, "%Y-%m-%d")
                    self.close_date = dt.strftime("%B %d, %Y")
        except Exception as e:
            logging.error("Failed to fetch Opportunity %s pre-call: %s", opp_id, e)

        self.set_persona(
            organization_name="Veritas Software",
            agent_name="Morgan",
            agent_purpose=(
                "to connect with customers ahead of their contract renewal, understand their "
                "intentions, and make sure the renewal process goes smoothly"
            ),
        )

        self.reach_person(
            contact_full_name=contact_name,
            on_success=self.begin_renewal_call,
            on_failure=self.recipient_unavailable,
        )

    def begin_renewal_call(self):
        amount_note = f" valued at {self.opp_amount}" if self.opp_amount else ""
        date_note = f" expiring on {self.close_date}" if self.close_date else " coming up for renewal"

        self.set_task(
            objective=(
                f"Speak with {self.contact_name} about renewing '{self.opp_name}'"
                f"{amount_note}{date_note}. Understand their renewal intent and any requested changes."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.contact_name}, this is Morgan from Veritas Software. "
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
            on_complete=self.record_outcome,
        )

    def record_outcome(self):
        intent = self.get_field("renewal_intent") or "need more time"
        changes = self.get_field("requested_changes") or ""
        reason = self.get_field("cancellation_reason") or ""
        followup = self.get_field("preferred_followup") or "email"

        new_stage = INTENT_TO_STAGE.get(intent, "Perception Analysis")

        description_lines = [
            f"Contract renewal call — {datetime.utcnow().strftime('%Y-%m-%d')}",
            f"Contact: {self.contact_name}",
            f"Intent: {intent}",
            f"Preferred follow-up: {followup}",
        ]
        if changes:
            description_lines.append(f"Requested changes: {changes}")
        if reason:
            description_lines.append(f"Cancellation reason: {reason}")

        logging.info(
            "Renewal call complete for opp %s — intent: %s, new stage: %s",
            self.opp_id, intent, new_stage,
        )

        try:
            update_opportunity(self.opp_id, {"StageName": new_stage})
            logging.info("Opportunity %s updated to stage: %s", self.opp_id, new_stage)
            log_task(
                self.opp_id,
                subject=f"Contract renewal call — {intent}",
                description="\n".join(description_lines),
            )
            logging.info("Task logged for opportunity %s.", self.opp_id)
        except Exception as e:
            logging.error("Failed to update Salesforce for opp %s: %s", self.opp_id, e)

        if intent == "not renewing":
            self.hangup(
                final_instructions=(
                    f"Thank {self.contact_name} sincerely for their past partnership. "
                    "Express that we're sorry to see them go and that their feedback has been "
                    "shared with the team. If they're open to it, let them know they're always "
                    "welcome back. Wish them well."
                )
            )
        elif intent == "renew with changes":
            self.hangup(
                final_instructions=(
                    f"Thank {self.contact_name} for their continued partnership. "
                    "Let them know the requested changes have been noted and an account executive "
                    "will send an updated proposal within two business days. "
                    "Confirm they'll receive it via their preferred method. Wish them a great day."
                )
            )
        else:
            email_note = "We'll send renewal paperwork via email. " if followup in ("email", "both") else ""
            call_note = "Someone will call to walk through it. " if followup in ("phone call", "both") else ""
            self.hangup(
                final_instructions=(
                    f"Thank {self.contact_name} and confirm the next steps. "
                    + email_note + call_note
                    + "Let them know they're in good hands and wish them a great day."
                )
            )

    def recipient_unavailable(self):
        logging.info(
            "Unable to reach %s for contract renewal call on opp %s.",
            self.contact_name, self.opp_id,
        )
        try:
            log_task(
                self.opp_id,
                subject="Contract renewal call — contact unavailable",
                description=(
                    f"Renewal outreach attempted — {self.contact_name} unavailable, voicemail left.\n"
                    f"Date: {datetime.utcnow().strftime('%Y-%m-%d')}"
                ),
            )
        except Exception as e:
            logging.error("Failed to log missed-call Task for opp %s: %s", self.opp_id, e)

        self.hangup(
            final_instructions=(
                f"Leave a professional voicemail for {self.contact_name} from Veritas Software. "
                f"Mention you're calling about their upcoming contract renewal for {self.opp_name} "
                "and that you'd love to connect. Ask them to call back or watch for an email. "
                "Keep it brief and warm."
            )
        )


if __name__ == "__main__":
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

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=ContractRenewalController(
            opp_id=args.opportunity_id,
            contact_name=args.name,
        ),
    )
