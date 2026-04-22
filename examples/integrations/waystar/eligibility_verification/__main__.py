import guava
import os
import logging
from guava import logging_utils
import json
import requests
from datetime import datetime, timezone


WAYSTAR_CLIENT_ID = os.environ["WAYSTAR_CLIENT_ID"]
WAYSTAR_CLIENT_SECRET = os.environ["WAYSTAR_CLIENT_SECRET"]
WAYSTAR_BASE_URL = os.environ.get("WAYSTAR_BASE_URL", "https://api.waystar.com")


def get_access_token() -> str:
    resp = requests.post(
        f"{WAYSTAR_BASE_URL}/auth/oauth2/token",
        data={
            "grant_type": "client_credentials",
            "client_id": WAYSTAR_CLIENT_ID,
            "client_secret": WAYSTAR_CLIENT_SECRET,
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def verify_eligibility(
    payer_id: str,
    provider_npi: str,
    member_id: str,
    first_name: str,
    last_name: str,
    date_of_birth: str,
    service_type: str = "30",
) -> dict:
    """Submits a real-time eligibility verification request to Waystar."""
    token = get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "payerId": payer_id,
        "provider": {
            "npi": provider_npi,
            "organizationName": "Riverside Family Medicine",
        },
        "subscriber": {
            "memberId": member_id,
            "firstName": first_name,
            "lastName": last_name,
            "dateOfBirth": date_of_birth,
        },
        "serviceTypes": [service_type],
        "dateOfService": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }
    resp = requests.post(
        f"{WAYSTAR_BASE_URL}/eligibility/v1/inquiries",
        headers=headers,
        json=payload,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def extract_coverage_summary(response: dict) -> dict:
    """Pulls key coverage data from the Waystar eligibility response."""
    summary = {
        "status": "unknown",
        "plan_name": "",
        "group_number": "",
        "copay": "",
        "deductible": "",
        "deductible_met": "",
        "out_of_pocket_max": "",
        "out_of_pocket_met": "",
    }
    coverage = response.get("coverages", [])
    for cov in coverage:
        cov_type = cov.get("coverageType", "")
        if cov_type == "ACTIVE":
            summary["status"] = "active"
            summary["plan_name"] = cov.get("planDescription", "")
            summary["group_number"] = cov.get("groupNumber", "")
        elif cov_type == "COPAY":
            summary["copay"] = cov.get("amount", "")
        elif cov_type == "DEDUCTIBLE":
            summary["deductible"] = cov.get("totalAmount", "")
            summary["deductible_met"] = cov.get("amountMet", "")
        elif cov_type == "OUT_OF_POCKET":
            summary["out_of_pocket_max"] = cov.get("totalAmount", "")
            summary["out_of_pocket_met"] = cov.get("amountMet", "")
    if not any(cov.get("coverageType") == "ACTIVE" for cov in coverage):
        summary["status"] = "inactive or not found"
    return summary


agent = guava.Agent(
    name="Taylor",
    organization="Riverside Family Medicine",
    purpose=(
        "to help patients and front-desk staff verify insurance eligibility "
        "before appointments using Waystar"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "run_eligibility",
        objective=(
            "A patient or staff member is calling to verify insurance eligibility. "
            "Collect the patient's insurance and identity details and run a real-time check."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Riverside Family Medicine. I'm Taylor, and I can "
                "verify your insurance coverage right now."
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
                field_type="text",
                description="Ask for the patient's date of birth in YYYY-MM-DD format.",
                required=True,
            ),
            guava.Field(
                key="member_id",
                field_type="text",
                description="Ask for their insurance member ID from their insurance card.",
                required=True,
            ),
            guava.Field(
                key="insurance_name",
                field_type="text",
                description="Ask which insurance company they're covered by.",
                required=True,
            ),
        ],
    )


@agent.on_task_complete("run_eligibility")
def on_done(call: guava.Call) -> None:
    first_name = call.get_field("first_name")
    last_name = call.get_field("last_name")
    dob = call.get_field("date_of_birth")
    member_id = call.get_field("member_id")
    insurance_name = call.get_field("insurance_name")

    payer_id = os.environ.get("WAYSTAR_PAYER_ID", "00001")
    provider_npi = os.environ["PROVIDER_NPI"]

    logging.info(
        "Waystar eligibility check for %s %s (DOB: %s, member: %s)",
        first_name, last_name, dob, member_id,
    )

    try:
        response = verify_eligibility(
            payer_id=payer_id,
            provider_npi=provider_npi,
            member_id=member_id,
            first_name=first_name,
            last_name=last_name,
            date_of_birth=dob,
        )
        coverage = extract_coverage_summary(response)
        logging.info("Waystar coverage result: %s", coverage)

        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": "Taylor",
            "use_case": "eligibility_verification",
            "patient": {"first_name": first_name, "last_name": last_name, "dob": dob},
            "member_id": member_id,
            "insurance": insurance_name,
            "coverage": coverage,
        }
        print(json.dumps(result, indent=2))

        status = coverage.get("status", "unknown")
        if status == "active":
            plan = coverage.get("plan_name") or insurance_name
            copay = coverage.get("copay", "")
            ded = coverage.get("deductible", "")
            ded_met = coverage.get("deductible_met", "")
            oop = coverage.get("out_of_pocket_max", "")
            oop_met = coverage.get("out_of_pocket_met", "")

            details = f"Your {plan} coverage is active."
            if copay:
                details += f" Expected copay: ${copay}."
            if ded:
                remaining = str(float(ded) - float(ded_met)) if ded_met else ""
                details += f" Deductible: ${ded}" + (f", ${remaining} remaining." if remaining else ".")
            if oop:
                oop_remaining = str(float(oop) - float(oop_met)) if oop_met else ""
                details += f" Out-of-pocket max: ${oop}" + (f", ${oop_remaining} remaining." if oop_remaining else ".")

            call.hangup(
                final_instructions=(
                    f"Let {first_name} know: {details} "
                    "Remind them to bring their insurance card and a photo ID to their "
                    "appointment. Thank them for calling Riverside Family Medicine."
                )
            )
        else:
            call.hangup(
                final_instructions=(
                    f"Let {first_name} know that we were unable to confirm active coverage "
                    f"for member ID {member_id} with {insurance_name}. "
                    "Ask them to verify the information on their insurance card or contact "
                    "their insurance company. Our billing team is also available to help. "
                    "Thank them for calling."
                )
            )
    except Exception as e:
        logging.error("Waystar eligibility check failed: %s", e)
        call.hangup(
            final_instructions=(
                f"Apologize to {first_name} for a technical issue and let them know "
                "we were unable to complete the eligibility check right now. Ask them to "
                "call back or contact their insurance company directly. Thank them for "
                "their patience."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
