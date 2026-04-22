import guava
import os
import logging
from guava import logging_utils
import argparse
import requests
from datetime import datetime, timezone


HUBSPOT_ACCESS_TOKEN = os.environ["HUBSPOT_ACCESS_TOKEN"]
HEADERS = {
    "Authorization": f"Bearer {HUBSPOT_ACCESS_TOKEN}",
    "Content-Type": "application/json",
}
BASE_URL = "https://api.hubapi.com"


def get_contact(contact_id: str) -> dict | None:
    resp = requests.get(
        f"{BASE_URL}/crm/objects/2026-03/contacts/{contact_id}",
        headers=HEADERS,
        params={"properties": "firstname,lastname,email,company,jobtitle"},
        timeout=10,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def log_followup_note(contact_id: str, note_body: str) -> None:
    """Creates a follow-up note associated with the contact."""
    payload = {
        "properties": {
            "hs_note_body": note_body,
            "hs_timestamp": datetime.now(timezone.utc).isoformat(),
        },
        "associations": [
            {
                "to": {"id": contact_id},
                "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 202}],
            }
        ],
    }
    resp = requests.post(
        f"{BASE_URL}/crm/objects/2026-03/notes",
        headers=HEADERS,
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()


def update_contact_lifecycle(contact_id: str, stage: str) -> None:
    resp = requests.patch(
        f"{BASE_URL}/crm/objects/2026-03/contacts/{contact_id}",
        headers=HEADERS,
        json={"properties": {"lifecyclestage": stage}},
        timeout=10,
    )
    resp.raise_for_status()


agent = guava.Agent(
    name="Alex",
    organization="Apex Solutions",
    purpose=(
        "to follow up with prospects after a meeting or demo and understand "
        "their reaction and next steps"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    contact_id = call.get_variable("contact_id")
    customer_name = call.get_variable("customer_name")
    meeting_topic = call.get_variable("meeting_topic")

    company = ""
    try:
        contact = get_contact(contact_id)
        if contact:
            company = contact.get("properties", {}).get("company") or ""
    except Exception as e:
        logging.error("Failed to fetch contact %s pre-call: %s", contact_id, e)

    call.company = company

    call.reach_person(contact_full_name=customer_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    customer_name = call.get_variable("customer_name")
    meeting_topic = call.get_variable("meeting_topic")
    contact_id = call.get_variable("contact_id")

    if outcome == "unavailable":
        logging.info("Unable to reach %s for meeting follow-up", customer_name)
        try:
            log_followup_note(
                contact_id,
                f"Post-meeting follow-up call attempted — {customer_name} not available, voicemail left. "
                f"Meeting topic: {meeting_topic}.",
            )
        except Exception as e:
            logging.error("Failed to log note for contact %s: %s", contact_id, e)

        call.hangup(
            final_instructions=(
                f"Leave a brief, warm voicemail for {customer_name} on behalf of Apex Solutions. "
                f"Let them know you're following up on your recent meeting about {meeting_topic} "
                "and that you'll send a quick email as well. "
                "Let them know they can reach you at the number you're calling from. "
                "Keep it friendly and brief."
            )
        )
    elif outcome == "available":
        company_note = f" at {call.company}" if call.company else ""

        call.set_task(
            "record_followup",
            objective=(
                f"Follow up with {customer_name}{company_note} after their recent meeting "
                f"about '{meeting_topic}'. Gauge their reaction, address any questions, "
                "and agree on a clear next step."
            ),
            checklist=[
                guava.Say(
                    f"Hi {customer_name}, this is Alex from Apex Solutions. "
                    f"I'm following up on our recent meeting about {meeting_topic}. "
                    "I just wanted to check in and see how you're feeling about everything we discussed."
                ),
                guava.Field(
                    key="overall_impression",
                    field_type="multiple_choice",
                    description="Ask how they felt about the meeting overall.",
                    choices=["very positive", "positive", "neutral", "had some concerns"],
                    required=True,
                ),
                guava.Field(
                    key="questions_or_concerns",
                    field_type="text",
                    description=(
                        "Ask if they have any questions or concerns from what was covered. "
                        "Capture the full question or concern if they have one."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="internal_alignment",
                    field_type="multiple_choice",
                    description=(
                        "Ask if they've had a chance to share what they learned with other "
                        "stakeholders internally."
                    ),
                    choices=[
                        "yes/positive reception",
                        "yes/more questions",
                        "not yet",
                        "not needed",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="next_step",
                    field_type="multiple_choice",
                    description="Ask what they see as a good next step.",
                    choices=[
                        "schedule another call",
                        "send a proposal",
                        "start a trial",
                        "need more time to evaluate",
                        "not moving forward",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="next_step_timing",
                    field_type="multiple_choice",
                    description="If a next step was agreed, ask when works best.",
                    choices=["this week", "next week", "within the month", "no rush"],
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("record_followup")
def on_done(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    meeting_topic = call.get_variable("meeting_topic")
    contact_id = call.get_variable("contact_id")

    impression = call.get_field("overall_impression") or "unknown"
    questions = call.get_field("questions_or_concerns") or ""
    alignment = call.get_field("internal_alignment") or "unknown"
    next_step = call.get_field("next_step") or "unknown"
    timing = call.get_field("next_step_timing") or ""

    note_lines = [
        f"Post-meeting follow-up — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
        f"Meeting topic: {meeting_topic}",
        f"Overall impression: {impression}",
        f"Internal alignment: {alignment}",
        f"Agreed next step: {next_step}",
    ]
    if timing:
        note_lines.append(f"Next step timing: {timing}")
    if questions:
        note_lines.append(f"Questions/concerns: {questions}")

    logging.info(
        "Meeting follow-up complete for contact %s — next step: %s",
        contact_id, next_step,
    )

    try:
        log_followup_note(contact_id, "\n".join(note_lines))
        if next_step in ("send a proposal", "start a trial", "schedule another call"):
            update_contact_lifecycle(contact_id, "opportunity")
        logging.info("Follow-up note saved for contact %s", contact_id)
    except Exception as e:
        logging.error("Failed to save follow-up note for contact %s: %s", contact_id, e)

    if next_step == "not moving forward":
        call.hangup(
            final_instructions=(
                f"Thank {customer_name} warmly for their time and for meeting with us. "
                "Respect their decision and let them know the door is always open if anything changes. "
                "Wish them all the best."
            )
        )
    else:
        timing_phrase = f" — ideally {timing}" if timing else ""
        call.hangup(
            final_instructions=(
                f"Confirm the agreed next step with {customer_name}: {next_step}{timing_phrase}. "
                "Let them know you'll send a follow-up email summarizing what was discussed. "
                "Thank them for their time and express genuine excitement. Wish them a great day."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(description="Outbound post-meeting follow-up call.")
    parser.add_argument("phone", help="Contact's phone number (E.164, e.g. +15551234567)")
    parser.add_argument("--contact-id", required=True, help="HubSpot contact ID")
    parser.add_argument("--name", required=True, help="Contact's full name")
    parser.add_argument(
        "--meeting-topic",
        required=True,
        help="Topic or title of the meeting (e.g. 'your product demo')",
    )
    args = parser.parse_args()

    logging.info("Initiating meeting follow-up call to %s (%s)", args.name, args.phone)

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "contact_id": args.contact_id,
            "customer_name": args.name,
            "meeting_topic": args.meeting_topic,
        },
    )
