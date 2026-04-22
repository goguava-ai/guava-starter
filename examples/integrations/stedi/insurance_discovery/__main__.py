import guava
import os
import logging
from guava import logging_utils
import argparse
import time
import requests


STEDI_API_KEY = os.environ["STEDI_API_KEY"]
PROVIDER_NPI = os.environ["STEDI_PROVIDER_NPI"]
PROVIDER_NAME = os.environ.get("STEDI_PROVIDER_NAME", "Ridgeline Health")
BASE_URL = "https://healthcare.us.stedi.com/2024-04-01"
HEADERS = {
    "Authorization": f"Key {STEDI_API_KEY}",
    "Content-Type": "application/json",
}


def submit_insurance_discovery(
    first_name: str, last_name: str, date_of_birth: str
) -> str:
    """Submits an insurance discovery request and returns the discovery ID."""
    payload = {
        "patient": {
            "firstName": first_name.upper(),
            "lastName": last_name.upper(),
            "dateOfBirth": date_of_birth.replace("-", ""),
        },
        "provider": {
            "npi": PROVIDER_NPI,
            "organizationName": PROVIDER_NAME,
        },
    }
    resp = requests.post(
        f"{BASE_URL}/insurance-discovery/check/v1",
        headers=HEADERS,
        json=payload,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["discoveryId"]


def poll_insurance_discovery(
    discovery_id: str, max_polls: int = 6, interval: float = 5.0
) -> dict | None:
    """Polls until the discovery is complete or max_polls is reached. Returns results or None."""
    for attempt in range(max_polls):
        resp = requests.get(
            f"{BASE_URL}/insurance-discovery/check/v1/{discovery_id}",
            headers=HEADERS,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status", "")
        logging.info(
            "Discovery %s status (attempt %d/%d): %s",
            discovery_id, attempt + 1, max_polls, status,
        )
        if status == "completed":
            return data
        if status == "failed":
            return None
        time.sleep(interval)
    return None


agent = guava.Agent(
    name="Casey",
    organization="Ridgeline Health",
    purpose=(
        "to help patients confirm or update their insurance information "
        "ahead of an upcoming appointment"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    first_name = call.get_variable("first_name")
    last_name = call.get_variable("last_name")
    date_of_birth = call.get_variable("date_of_birth")

    # Submit and poll for insurance discovery before the call connects so results
    # are ready when the patient picks up.
    discovery_result = None
    try:
        discovery_id = submit_insurance_discovery(first_name, last_name, date_of_birth)
        logging.info("Insurance discovery submitted: %s", discovery_id)
        discovery_result = poll_insurance_discovery(discovery_id)
        if discovery_result:
            plans = discovery_result.get("insurancePlans", [])
            logging.info("Discovery complete — %d plan(s) found", len(plans))
        else:
            logging.warning(
                "Discovery did not complete before call for patient %s", patient_name
            )
    except Exception as e:
        logging.error("Insurance discovery submission failed: %s", e)

    call.set_variable("discovery_result", discovery_result)
    call.set_variable("confirmed_payer", "")
    call.set_variable("confirmed_plan_details", "")

    call.reach_person(contact_full_name=patient_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    patient_name = call.get_variable("patient_name")

    if outcome == "unavailable":
        logging.info("Unable to reach %s for insurance discovery", patient_name)
        call.hangup(
            final_instructions=(
                f"Leave a brief, friendly voicemail for {patient_name} on behalf of "
                "Ridgeline Health. Let them know you're calling to verify their insurance "
                "ahead of their upcoming appointment and ask them to call back at their "
                "convenience, or to bring their insurance card to the visit. Keep it brief."
            )
        )
    elif outcome == "available":
        if not call.get_variable("discovery_result"):
            # Discovery didn't complete in time — ask the patient for their info directly
            call.set_task(
                "save_insurance_info",
                objective=(
                    f"We were unable to automatically locate insurance on file for {patient_name}. "
                    "Ask them to provide their insurance details so we can update their record."
                ),
                checklist=[
                    guava.Say(
                        f"Hi {patient_name}, this is Casey calling from Ridgeline Health "
                        "about your upcoming appointment. I was trying to verify your insurance "
                        "coverage ahead of your visit but I'm having trouble locating your plan."
                    ),
                    guava.Field(
                        key="has_insurance",
                        field_type="multiple_choice",
                        description="Ask if they currently have health insurance.",
                        choices=["yes", "no", "not sure"],
                        required=True,
                    ),
                    guava.Field(
                        key="insurer_name",
                        field_type="text",
                        description="If yes, ask which insurance company they're with.",
                        required=False,
                    ),
                    guava.Field(
                        key="member_id",
                        field_type="text",
                        description="Ask for their member ID if they have it handy.",
                        required=False,
                    ),
                ],
            )
            return

        plans = (call.get_variable("discovery_result") or {}).get("insurancePlans", [])

        if not plans:
            call.set_task(
                "handle_no_coverage",
                objective=(
                    f"Insurance discovery found no active plans for {patient_name}. "
                    "Let them know and ask how they'd like to proceed."
                ),
                checklist=[
                    guava.Say(
                        f"Hi {patient_name}, this is Casey from Ridgeline Health. "
                        "I'm calling about your upcoming appointment. When I checked your "
                        "insurance coverage, I wasn't able to find an active plan on file."
                    ),
                    guava.Field(
                        key="no_coverage_preference",
                        field_type="multiple_choice",
                        description=(
                            "Ask how they'd like to proceed — self-pay, provide insurance details, "
                            "or speak with our billing team."
                        ),
                        choices=["self-pay", "provide insurance details", "speak with billing"],
                        required=True,
                    ),
                ],
            )
            return

        # Plan(s) found — confirm with the patient
        plan = plans[0]
        payer_name = plan.get("payerName", "an insurer")
        member_id = plan.get("memberId", "")
        group_number = plan.get("groupNumber", "")

        confirmed_plan_details = payer_name
        if member_id:
            confirmed_plan_details += f", member ID {member_id}"
        if group_number:
            confirmed_plan_details += f", group {group_number}"
        call.set_variable("confirmed_payer", payer_name)
        call.set_variable("confirmed_plan_details", confirmed_plan_details)

        member_note = f" with member ID {member_id}" if member_id else ""

        call.set_task(
            "finalize_confirmation",
            objective=(
                f"We found a {payer_name} plan on file for {patient_name}. "
                "Confirm this is correct so we have the right coverage for their visit."
            ),
            checklist=[
                guava.Say(
                    f"Hi {patient_name}, this is Casey calling from Ridgeline Health. "
                    f"I'm reaching out ahead of your upcoming appointment. I was able to locate "
                    f"a {payer_name} plan on file for you{member_note}."
                ),
                guava.Field(
                    key="plan_confirmed",
                    field_type="multiple_choice",
                    description=(
                        f"Ask if their {payer_name} plan{member_note} sounds correct."
                    ),
                    choices=["yes, that's correct", "no, that's not right"],
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("finalize_confirmation")
def finalize_confirmation(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    confirmed = call.get_field("plan_confirmed") or ""
    if "yes" in confirmed.lower():
        logging.info(
            "Patient confirmed coverage: %s", call.get_variable("confirmed_plan_details")
        )
        call.hangup(
            final_instructions=(
                f"Let {patient_name} know their {call.get_variable('confirmed_payer')} coverage "
                "is confirmed and we'll have it ready at check-in. "
                "Remind them to bring their insurance card. "
                "Thank them for their time and wish them well."
            )
        )
    else:
        logging.info(
            "Patient did not confirm plan on file — flagging for billing team"
        )
        call.hangup(
            final_instructions=(
                f"Acknowledge that the plan on file doesn't match what {patient_name} "
                "has. Let them know our billing team will reach out to get the correct "
                "information before their appointment. Ask them to bring their current "
                "insurance card to the visit. Thank them for letting us know."
            )
        )


@agent.on_task_complete("save_insurance_info")
def save_insurance_info(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    has_insurance = call.get_field("has_insurance") or "not sure"
    insurer = call.get_field("insurer_name") or ""
    member_id = call.get_field("member_id") or ""
    logging.info(
        "Insurance info from patient — has: %s, insurer: %s, member: %s",
        has_insurance, insurer, member_id,
    )

    if has_insurance == "yes" and insurer:
        call.hangup(
            final_instructions=(
                f"Thank {patient_name} for providing their insurance details. "
                "Let them know our billing team will verify and add this to their record "
                "before their appointment. Ask them to bring their insurance card to the visit. "
                "Thank them for their time."
            )
        )
    elif has_insurance == "no":
        call.hangup(
            final_instructions=(
                f"Acknowledge that {patient_name} doesn't have insurance. "
                "Let them know we offer self-pay options and our team can discuss payment plans. "
                "Thank them for letting us know and wish them well."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Let {patient_name} know our billing team will follow up to confirm "
                "their insurance before the appointment. Ask them to bring any insurance cards "
                "they have to the visit. Thank them for their time."
            )
        )


@agent.on_task_complete("handle_no_coverage")
def handle_no_coverage(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    preference = call.get_field("no_coverage_preference") or ""
    logging.info(
        "No-coverage outcome for %s: %s", patient_name, preference
    )

    if "billing" in preference:
        call.hangup(
            final_instructions=(
                f"Let {patient_name} know a billing specialist will call them back "
                "within one business day to discuss their options. Thank them for their time."
            )
        )
    elif "insurance" in preference:
        call.hangup(
            final_instructions=(
                f"Ask {patient_name} to call us back with their insurance details, "
                "or bring their card to the appointment. Thank them for their time."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Let {patient_name} know we've noted they'll be self-pay for this visit. "
                "Mention that our team can walk them through payment options at check-in. "
                "Thank them for their time."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound insurance discovery call for a patient ahead of an appointment."
    )
    parser.add_argument("phone", help="Patient phone number (E.164, e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Patient's full name")
    parser.add_argument("--first-name", required=True, help="Patient's first name")
    parser.add_argument("--last-name", required=True, help="Patient's last name")
    parser.add_argument("--dob", required=True, help="Date of birth (YYYY-MM-DD)")
    args = parser.parse_args()

    logging.info(
        "Initiating insurance discovery call to %s (%s)", args.name, args.phone
    )

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "patient_name": args.name,
            "first_name": args.first_name,
            "last_name": args.last_name,
            "date_of_birth": args.dob,
        },
    )
