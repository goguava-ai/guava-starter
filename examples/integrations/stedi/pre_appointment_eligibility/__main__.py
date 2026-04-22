import argparse
import logging
import os
import random
from datetime import date

import guava
import requests
from guava import logging_utils

STEDI_API_KEY = os.environ["STEDI_API_KEY"]
PROVIDER_NPI = os.environ["STEDI_PROVIDER_NPI"]
PROVIDER_NAME = os.environ.get("STEDI_PROVIDER_NAME", "Ridgeline Health")
BASE_URL = "https://healthcare.us.stedi.com/2024-04-01"
HEADERS = {
    "Authorization": f"Key {STEDI_API_KEY}",
    "Content-Type": "application/json",
}


def check_eligibility(
    trading_partner_id: str,
    member_id: str,
    first_name: str,
    last_name: str,
    date_of_birth: str,
) -> dict:
    """Posts a real-time eligibility check (270/271) to Stedi and returns the parsed response."""
    payload = {
        "controlNumber": str(random.randint(100000000, 999999999)),
        "tradingPartnerServiceId": trading_partner_id,
        "provider": {
            "organizationName": PROVIDER_NAME,
            "npi": PROVIDER_NPI,
        },
        "subscriber": {
            "memberId": member_id,
            "firstName": first_name.upper(),
            "lastName": last_name.upper(),
            "dateOfBirth": date_of_birth.replace("-", ""),
        },
        "encounter": {
            "serviceTypeCodes": ["30"],
            "dateOfService": date.today().strftime("%Y%m%d"),
        },
    }
    resp = requests.post(
        f"{BASE_URL}/change/medicalnetwork/eligibility/v3",
        headers=HEADERS,
        json=payload,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


agent = guava.Agent(
    name="Riley",
    organization="Ridgeline Health",
    purpose=(
        "to confirm upcoming appointments and alert patients to any insurance issues "
        "that need to be resolved before their visit"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    first_name = call.get_variable("first_name")
    last_name = call.get_variable("last_name")
    date_of_birth = call.get_variable("date_of_birth")
    member_id = call.get_variable("member_id")
    payer_id = call.get_variable("payer_id")
    appointment_date = call.get_variable("appointment_date")

    # Run the eligibility check before the call connects so results are ready
    # when the patient picks up. This avoids any wait time mid-call.
    eligibility_active = None
    plan_name = "their insurance plan"
    try:
        result = check_eligibility(
            payer_id, member_id, first_name, last_name, date_of_birth
        )
        plan_info = result.get("planInformation", {})
        plan_name = plan_info.get("planDescription") or plan_name
        for status in result.get("planStatus", []):
            code = status.get("statusCode", "")
            if code == "1":
                eligibility_active = True
                break
            elif code == "6":
                eligibility_active = False
                break
        logging.info(
            "Pre-call eligibility for %s: active=%s, plan=%s",
            patient_name, eligibility_active, plan_name,
        )
    except Exception as e:
        logging.error("Pre-call eligibility check failed for %s: %s", patient_name, e)
        eligibility_active = None

    call.set_variable("eligibility_active", eligibility_active)
    call.set_variable("plan_name", plan_name)

    call.reach_person(contact_full_name=patient_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    patient_name = call.get_variable("patient_name")
    appointment_date = call.get_variable("appointment_date")

    if outcome == "unavailable":
        logging.info(
            "Unable to reach %s for pre-appointment eligibility", patient_name
        )
        eligibility_active = call.get_variable("eligibility_active")
        if eligibility_active is True:
            coverage_note = "their coverage looks good and no action is needed"
        elif eligibility_active is False:
            coverage_note = (
                "there may be an issue with their insurance coverage — they should "
                "bring an updated card or contact their insurer before the visit"
            )
        else:
            coverage_note = "they should bring their insurance card to check-in"

        call.hangup(
            final_instructions=(
                f"Leave a brief, friendly voicemail for {patient_name} from Ridgeline Health. "
                f"Let them know you're calling about their appointment on {appointment_date} "
                f"and that {coverage_note}. "
                "Ask them to call back if they have any questions. Keep it concise."
            )
        )
    elif outcome == "available":
        eligibility_active = call.get_variable("eligibility_active")
        plan_name = call.get_variable("plan_name")
        if eligibility_active is True:
            call.hangup(
                final_instructions=(
                    f"Greet {patient_name} warmly. Let them know you're calling from "
                    f"Ridgeline Health about their appointment on {appointment_date}. "
                    f"Tell them you've verified their {plan_name} coverage and everything "
                    "looks good — no action needed. Remind them to bring their insurance card "
                    "and a photo ID, and to arrive 10 minutes early. Wish them a great visit."
                )
            )

        elif eligibility_active is False:
            call.set_task(
                "handle_inactive_coverage",
                objective=(
                    f"Coverage for {patient_name} came back inactive ahead of their "
                    f"appointment on {appointment_date}. Let them know and agree on next steps."
                ),
                checklist=[
                    guava.Say(
                        f"Hi {patient_name}, this is Riley calling from Ridgeline Health. "
                        f"I'm reaching out ahead of your appointment on {appointment_date}. "
                        "When we verified your insurance today, we weren't able to confirm active "
                        f"coverage under {plan_name}. I wanted to give you a heads-up so "
                        "there are no surprises at check-in."
                    ),
                    guava.Field(
                        key="resolution_preference",
                        field_type="multiple_choice",
                        description="Ask how they'd like to handle this before their visit.",
                        choices=[
                            "I'll contact my insurance company",
                            "I'll bring a different insurance card",
                            "I'd like to proceed as self-pay",
                            "please have billing call me",
                        ],
                        required=True,
                    ),
                ],
            )

        else:
            # Eligibility check was inconclusive — still call to confirm the appointment
            call.hangup(
                final_instructions=(
                    f"Greet {patient_name} from Ridgeline Health. "
                    f"Let them know you're calling to confirm their appointment on {appointment_date}. "
                    "Mention they should bring their insurance card and photo ID. "
                    "Let them know our team will verify their coverage at check-in. "
                    "Thank them and wish them well."
                )
            )


@agent.on_task_complete("handle_inactive_coverage")
def handle_inactive_coverage(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    appointment_date = call.get_variable("appointment_date")
    preference = call.get_field("resolution_preference") or ""
    logging.info(
        "Inactive coverage resolution for %s: %s", patient_name, preference
    )

    if "billing call" in preference:
        call.hangup(
            final_instructions=(
                f"Thank {patient_name} — let them know a billing specialist will "
                "call them back within one business day. Confirm their appointment is still "
                f"scheduled for {appointment_date} and wish them well."
            )
        )
    elif "self-pay" in preference:
        call.hangup(
            final_instructions=(
                f"Acknowledge {patient_name}'s choice to proceed as self-pay. "
                "Let them know our team can walk them through pricing and payment options "
                f"when they arrive. Confirm their appointment for {appointment_date}. "
                "Thank them and wish them a great visit."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {patient_name} for letting us know. Remind them to bring "
                f"an updated insurance card to their appointment on {appointment_date}. "
                "Let them know our front desk team will re-verify their coverage at check-in. "
                "Wish them well."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound pre-appointment eligibility verification call."
    )
    parser.add_argument("phone", help="Patient phone number (E.164, e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Patient's full name")
    parser.add_argument("--first-name", required=True, help="Patient's first name")
    parser.add_argument("--last-name", required=True, help="Patient's last name")
    parser.add_argument("--dob", required=True, help="Date of birth (YYYY-MM-DD)")
    parser.add_argument("--member-id", required=True, help="Insurance member ID")
    parser.add_argument("--payer-id", required=True, help="Stedi trading partner ID")
    parser.add_argument(
        "--appointment-date",
        required=True,
        help="Appointment date for the patient to hear (e.g. 'March 27th at 2:00 PM')",
    )
    args = parser.parse_args()

    logging.info(
        "Initiating pre-appointment eligibility call to %s (%s) for %s",
        args.name, args.phone, args.appointment_date,
    )

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "patient_name": args.name,
            "first_name": args.first_name,
            "last_name": args.last_name,
            "date_of_birth": args.dob,
            "member_id": args.member_id,
            "payer_id": args.payer_id,
            "appointment_date": args.appointment_date,
        },
    )
