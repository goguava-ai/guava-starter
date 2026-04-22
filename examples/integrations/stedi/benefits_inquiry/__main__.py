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

# Maps human-readable service types to X12 270 service type codes
SERVICE_TYPE_CODES: dict[str, list[str]] = {
    "primary care visit": ["1", "30"],
    "specialist visit": ["1", "30"],
    "hospital stay": ["47", "48"],
    "urgent care": ["UC"],
    "mental health": ["MH"],
    "prescription drugs": ["88"],
}


def check_eligibility(
    trading_partner_id: str,
    member_id: str,
    first_name: str,
    last_name: str,
    date_of_birth: str,
    service_type_codes: list[str],
) -> dict:
    """Posts a real-time eligibility check (270/271) to Stedi for specific service types."""
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
            "serviceTypeCodes": service_type_codes,
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


def extract_benefits_summary(response: dict) -> dict[str, str]:
    """Parses benefitsInformation from an eligibility response into a readable summary.

    Benefit codes: C = Deductible, G = Out-of-Pocket Max, B = Copayment, A = Coinsurance.
    """
    summary: dict[str, str] = {}
    for benefit in response.get("benefitsInformation", []):
        code = benefit.get("code", "")
        amount = benefit.get("benefitAmount")
        percent = benefit.get("benefitPercent")
        network = benefit.get("inPlanNetworkIndicatorCode", "")
        network_label = (
            "in_network" if network == "Y" else ("out_of_network" if network == "N" else "")
        )

        if code == "C" and amount:
            key = f"deductible{'_' + network_label if network_label else ''}"
            summary.setdefault(key, f"${float(amount):,.2f}")
        elif code == "G" and amount:
            key = f"out_of_pocket_max{'_' + network_label if network_label else ''}"
            summary.setdefault(key, f"${float(amount):,.2f}")
        elif code == "B" and amount:
            key = f"copay{'_' + network_label if network_label else ''}"
            summary.setdefault(key, f"${float(amount):,.2f}")
        elif code == "A" and percent:
            key = f"coinsurance{'_' + network_label if network_label else ''}"
            summary.setdefault(key, f"{float(percent) * 100:.0f}%")

    return summary


agent = guava.Agent(
    name="Jordan",
    organization="Ridgeline Health",
    purpose=(
        "to help patients understand their insurance benefits — including their copay, "
        "deductible, and out-of-pocket maximum — before an upcoming service"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "lookup_benefits",
        objective=(
            "A patient has called to find out what they'll owe for an upcoming service. "
            "Collect their insurance details and the service type so we can look up their benefits."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Ridgeline Health. I'm Jordan. "
                "I can look up your specific benefits so you know exactly what to expect at your visit."
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
                description="Ask for their insurance member ID from their card.",
                required=True,
            ),
            guava.Field(
                key="payer_id",
                field_type="text",
                description="Ask which insurance company they have.",
                required=True,
            ),
            guava.Field(
                key="service_type",
                field_type="multiple_choice",
                description=(
                    "Ask what type of service they're coming in for. For example: "
                    "a primary care visit, specialist visit, hospital stay, urgent care, "
                    "mental health appointment, or prescription drugs."
                ),
                choices=list(SERVICE_TYPE_CODES.keys()),
                required=True,
            ),
        ],
    )


@agent.on_task_complete("lookup_benefits")
def lookup_benefits(call: guava.Call) -> None:
    first_name = call.get_field("first_name") or ""
    last_name = call.get_field("last_name") or ""
    dob = call.get_field("date_of_birth") or ""
    member_id = call.get_field("member_id") or ""
    payer_id = call.get_field("payer_id") or ""
    service_type = call.get_field("service_type") or "primary care visit"

    codes = SERVICE_TYPE_CODES.get(service_type, ["30"])
    logging.info(
        "Looking up benefits — patient: %s %s, service: %s, codes: %s",
        first_name, last_name, service_type, codes,
    )

    try:
        result = check_eligibility(payer_id, member_id, first_name, last_name, dob, codes)
        benefits = extract_benefits_summary(result)
    except Exception as e:
        logging.error("Stedi benefits lookup failed: %s", e)
        call.hangup(
            final_instructions=(
                f"Apologize to {first_name} — there was a technical issue retrieving their benefits. "
                "Ask them to call the member services number on the back of their insurance card "
                "for specific cost-sharing details. Thank them for their patience."
            )
        )
        return

    if not benefits:
        call.hangup(
            final_instructions=(
                f"Let {first_name} know we found their coverage but couldn't retrieve specific "
                f"benefit details for {service_type} from their plan. "
                "Recommend they call the member services number on their insurance card "
                "for exact cost-sharing amounts."
            )
        )
        return

    benefits_lines = ", ".join(
        f"{k.replace('_', ' ')}: {v}" for k, v in benefits.items()
    )
    logging.info("Benefits found for %s %s: %s", first_name, last_name, benefits)

    call.hangup(
        final_instructions=(
            f"Share {first_name}'s benefits for a {service_type}: {benefits_lines}. "
            "Briefly explain each term — a copay is a flat fee at the time of service, "
            "a deductible is what they pay before insurance starts covering costs, "
            "and coinsurance is the percentage they pay after meeting their deductible. "
            "Note that exact costs may vary and they should confirm with their insurer. "
            "Thank them for calling Ridgeline Health."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
