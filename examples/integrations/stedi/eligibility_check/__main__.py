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
    service_type_codes: list[str] | None = None,
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
            "serviceTypeCodes": service_type_codes or ["30"],
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


def is_coverage_active(response: dict) -> tuple[bool, str]:
    """Returns (is_active, plan_name) from an eligibility response."""
    plan_name = (
        response.get("planInformation", {}).get("planDescription") or "your insurance plan"
    )
    for status in response.get("planStatus", []):
        code = status.get("statusCode", "")
        if code == "1":  # Active Coverage
            return True, plan_name
        if code == "6":  # Inactive
            return False, plan_name
    return False, plan_name


agent = guava.Agent(
    name="Alex",
    organization="Ridgeline Health",
    purpose=(
        "to help patients confirm their insurance coverage is active "
        "before their upcoming visit"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "run_eligibility_check",
        objective=(
            "A patient has called to verify their insurance before an appointment. "
            "Collect their insurance card details and run an eligibility check."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Ridgeline Health. I'm Alex. "
                "I can verify your insurance right now — I just need a few details from your card."
            ),
            guava.Field(
                key="first_name",
                field_type="text",
                description="Ask for the patient's first name.",
                required=True,
            ),
            guava.Field(
                key="last_name",
                field_type="text",
                description="Ask for the patient's last name.",
                required=True,
            ),
            guava.Field(
                key="date_of_birth",
                field_type="date",
                description="Ask for their date of birth.",
                required=True,
            ),
            guava.Field(
                key="member_id",
                field_type="text",
                description=(
                    "Ask for their insurance member ID. "
                    "Let them know this appears on their insurance card."
                ),
                required=True,
            ),
            guava.Field(
                key="payer_id",
                field_type="text",
                description=(
                    "Ask which insurance company they have — for example, Aetna, "
                    "UnitedHealthcare, BlueCross BlueShield, Cigna, or Humana. "
                    "Capture the insurer name or trading partner ID."
                ),
                required=True,
            ),
        ],
    )


@agent.on_task_complete("run_eligibility_check")
def run_eligibility_check(call: guava.Call) -> None:
    first_name = call.get_field("first_name") or ""
    last_name = call.get_field("last_name") or ""
    dob = call.get_field("date_of_birth") or ""
    member_id = call.get_field("member_id") or ""
    payer_id = call.get_field("payer_id") or ""

    logging.info(
        "Checking eligibility — patient: %s %s, payer: %s, member: %s",
        first_name, last_name, payer_id, member_id,
    )

    try:
        result = check_eligibility(payer_id, member_id, first_name, last_name, dob)
        active, plan_name = is_coverage_active(result)
    except Exception as e:
        logging.error("Stedi eligibility check failed: %s", e)
        call.hangup(
            final_instructions=(
                f"Apologize to {first_name} — there was a technical issue verifying their "
                "coverage. Ask them to bring their insurance card to the appointment and we "
                "will verify at check-in. Thank them for their patience."
            )
        )
        return

    if active:
        logging.info("Active coverage confirmed — plan: %s", plan_name)
        call.hangup(
            final_instructions=(
                f"Let {first_name} know their coverage under {plan_name} is currently active. "
                "Remind them to bring their insurance card to the appointment. "
                "Thank them for calling Ridgeline Health."
            )
        )
    else:
        logging.info("Coverage not confirmed active — plan: %s", plan_name)
        call.hangup(
            final_instructions=(
                f"Let {first_name} know we were unable to confirm active coverage under "
                f"{plan_name} with the details they provided. "
                "Suggest they double-check their member ID or contact their insurer directly. "
                "Let them know our billing team is also available to help. Be empathetic."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
