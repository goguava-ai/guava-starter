import guava
import os
import logging
from guava import logging_utils
import argparse
import requests



def get_access_token() -> str:
    resp = requests.post(
        os.environ["NEXTGEN_TOKEN_URL"],
        data={"grant_type": "client_credentials", "scope": "system/*.read system/*.write"},
        auth=(os.environ["NEXTGEN_CLIENT_ID"], os.environ["NEXTGEN_CLIENT_SECRET"]),
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def post_communication(patient_id: str, specialty: str, intent: str, headers: dict) -> bool:
    base_url = os.environ["NEXTGEN_BASE_URL"]
    payload = {
        "resourceType": "Communication",
        "status": "completed",
        "subject": {"reference": f"Patient/{patient_id}"},
        "reasonCode": [{"text": f"Referral followup: {specialty}"}],
        "note": [{"text": f"Patient scheduling intent: {intent}"}],
    }
    resp = requests.post(f"{base_url}/Communication", headers=headers, json=payload, timeout=10)
    return resp.ok


agent = guava.Agent(
    name="Morgan",
    organization="Metro Specialty Clinic",
    purpose=(
        "to follow up with patients who received specialist referrals and ensure they've connected with the specialist"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(contact_full_name=call.get_variable("patient_name"))


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    patient_name = call.get_variable("patient_name")
    referral_specialty = call.get_variable("referral_specialty")

    if outcome == "unavailable":
        logging.info("Unable to reach %s for referral followup.", patient_name)
        call.hangup(
            final_instructions=(
                f"Leave a brief voicemail for {patient_name} from Metro Specialty Clinic. "
                f"Let them know you're following up on their referral to {referral_specialty} "
                "and ask them to call back if they have any questions or need help scheduling. "
                "Keep it brief and warm."
            )
        )
    elif outcome == "available":
        try:
            token = get_access_token()
            call.set_variable("headers", {"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        except Exception as e:
            logging.error("Token error: %s", e)
            call.set_variable("headers", {})

        call.set_task(
            "referral_followup",
            objective=(
                f"Follow up with {patient_name} on their referral to {referral_specialty}. "
                "Confirm they received it, check if they've scheduled with the specialist, "
                "and identify any barriers."
            ),
            checklist=[
                guava.Say(
                    f"Hi {patient_name}, this is Morgan calling from Metro Specialty Clinic. "
                    f"I'm following up on the referral we sent over to {referral_specialty}. "
                    "I just wanted to make sure you received it and check in on how things are going."
                ),
                guava.Field(
                    key="received_referral",
                    field_type="multiple_choice",
                    description=f"Ask if they received the referral to {referral_specialty}.",
                    choices=["yes", "no"],
                    required=True,
                ),
                guava.Field(
                    key="appointment_scheduled",
                    field_type="multiple_choice",
                    description=f"Ask if they've scheduled an appointment with the {referral_specialty} specialist.",
                    choices=["yes, scheduled", "not yet", "no, had trouble"],
                    required=True,
                ),
                guava.Field(
                    key="appointment_date",
                    field_type="text",
                    description=(
                        "If they have scheduled, ask when the appointment is. "
                        "Skip if they haven't scheduled yet."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="barriers",
                    field_type="text",
                    description=(
                        "If they haven't scheduled or had trouble, ask what's getting in the way. "
                        "Skip if already scheduled."
                    ),
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("referral_followup")
def on_referral_followup_done(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    patient_id = call.get_variable("patient_id")
    referral_specialty = call.get_variable("referral_specialty")

    received = call.get_field("received_referral") or ""
    scheduled = call.get_field("appointment_scheduled") or ""
    appt_date = call.get_field("appointment_date") or ""
    barriers = call.get_field("barriers") or ""

    logging.info(
        "Referral followup — patient %s, specialty: %s, received: %s, scheduled: %s",
        patient_id, referral_specialty, received, scheduled,
    )

    intent = f"received={received}, scheduled={scheduled}, date={appt_date}, barriers={barriers}"

    try:
        post_communication(patient_id, referral_specialty, intent, call.get_variable("headers"))
    except Exception as e:
        logging.error("Failed to log Communication: %s", e)

    if "yes, scheduled" in scheduled and appt_date:
        call.hangup(
            final_instructions=(
                f"Great — let {patient_name} know you're glad they've got the appointment set "
                f"for {appt_date} with the {referral_specialty} specialist. "
                "Let them know the care team is here if they have any questions before then. "
                "Wish them a great day."
            )
        )
    elif "trouble" in scheduled or barriers:
        call.hangup(
            final_instructions=(
                f"Empathize with {patient_name} about the difficulty. "
                "Let them know you'll flag their barriers to the care coordinator, who will "
                "reach out with help finding an in-network specialist. "
                "Thank them for letting us know and wish them well."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Encourage {patient_name} to reach out to the {referral_specialty} "
                "specialist at their earliest convenience. Let them know the referral should be "
                "on file with the specialist's office. They can also call us if they need help "
                "navigating the process. Thank them and wish them a great day."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(description="Outbound referral followup via NextGen FHIR.")
    parser.add_argument("phone", help="Patient phone number (E.164)")
    parser.add_argument("--name", required=True)
    parser.add_argument("--patient-id", required=True)
    parser.add_argument("--referral-specialty", required=True, help="Specialist referral type (e.g. 'Cardiology')")
    args = parser.parse_args()

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "patient_name": args.name,
            "patient_id": args.patient_id,
            "referral_specialty": args.referral_specialty,
        },
    )
