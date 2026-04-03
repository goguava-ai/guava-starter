import guava
import os
import logging
import json
import argparse
import requests
from datetime import datetime

logging.basicConfig(level=logging.INFO)

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


def get_claim_detail(claim_id: str) -> dict | None:
    """Fetches the full claim detail from Waystar by claim ID."""
    token = get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    resp = requests.get(
        f"{WAYSTAR_BASE_URL}/claims/v1/{claim_id}",
        headers=headers,
        timeout=10,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def update_claim_followup_status(claim_id: str, outcome: str) -> None:
    """Records the patient notification outcome on the claim in Waystar."""
    token = get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    requests.patch(
        f"{WAYSTAR_BASE_URL}/claims/v1/{claim_id}",
        headers=headers,
        json={
            "workflowStatus": "patient_notified",
            "notes": f"Patient notified of denial on {datetime.utcnow().strftime('%Y-%m-%d')}: {outcome}",
        },
        timeout=10,
    )


class DenialNotificationController(guava.CallController):
    def __init__(
        self,
        patient_name: str,
        claim_id: str,
        denial_reason: str,
        service_description: str,
        service_date: str,
        claim_amount: str,
    ):
        super().__init__()
        self.patient_name = patient_name
        self.claim_id = claim_id
        self.denial_reason = denial_reason
        self.service_description = service_description
        self.service_date = service_date
        self.claim_amount = claim_amount

        self.set_persona(
            organization_name="Riverside Family Medicine Billing",
            agent_name="Alex",
            agent_purpose=(
                "to notify patients about insurance claim denials and help them understand "
                "their options for next steps"
            ),
        )

        self.reach_person(
            contact_full_name=self.patient_name,
            on_success=self.deliver_notification,
            on_failure=self.recipient_unavailable,
        )

    def deliver_notification(self):
        first_name = self.patient_name.split()[0] if self.patient_name else "there"

        self.set_task(
            objective=(
                f"Notify {self.patient_name} that their insurance claim for "
                f"'{self.service_description}' on {self.service_date} was denied. "
                "Explain the denial reason and gather their preferred next step."
            ),
            checklist=[
                guava.Say(
                    f"Hi {first_name}, this is Alex calling from Riverside Family Medicine "
                    "billing. I'm calling with an important update about an insurance claim "
                    f"for your visit on {self.service_date}."
                ),
                guava.Field(
                    key="understood_denial",
                    field_type="multiple_choice",
                    description=(
                        f"Explain that insurance claim {self.claim_id} for "
                        f"'{self.service_description}' (${self.claim_amount}) was denied "
                        f"with the reason: '{self.denial_reason}'. Ask if they understand "
                        "and would like to hear their options."
                    ),
                    choices=["yes, please explain my options", "no, I have questions first"],
                    required=True,
                ),
                guava.Field(
                    key="preferred_next_step",
                    field_type="multiple_choice",
                    description=(
                        "Explain the options: we can file an appeal with the insurance company, "
                        "they can contact their insurance company directly, or they can arrange "
                        "to pay the balance directly. Ask which they prefer."
                    ),
                    choices=[
                        "file an appeal on my behalf",
                        "I will contact my insurance company",
                        "arrange self-pay",
                        "I need more time to decide",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="additional_questions",
                    field_type="text",
                    description=(
                        "Ask if they have any other questions about the denial or the billing "
                        "process. Capture any concerns they raise."
                    ),
                    required=False,
                ),
            ],
            on_complete=self.record_outcome,
        )

    def record_outcome(self):
        next_step = self.get_field("preferred_next_step")
        questions = self.get_field("additional_questions") or ""
        first_name = self.patient_name.split()[0] if self.patient_name else "there"

        logging.info(
            "Denial notification outcome for claim %s: next_step=%s",
            self.claim_id, next_step,
        )

        outcome = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "agent": "Alex",
            "use_case": "denial_notification",
            "patient_name": self.patient_name,
            "claim_id": self.claim_id,
            "denial_reason": self.denial_reason,
            "service_description": self.service_description,
            "service_date": self.service_date,
            "claim_amount": self.claim_amount,
            "preferred_next_step": next_step,
            "additional_questions": questions,
        }
        print(json.dumps(outcome, indent=2))

        try:
            update_claim_followup_status(self.claim_id, next_step)
            logging.info("Waystar claim %s updated with notification outcome", self.claim_id)
        except Exception as e:
            logging.warning("Failed to update Waystar claim status: %s", e)

        if next_step == "file an appeal on my behalf":
            self.hangup(
                final_instructions=(
                    f"Let {first_name} know that we will file an appeal with their insurance "
                    "company on their behalf. The appeal process typically takes 30 to 60 days. "
                    "Let them know our billing team will contact them with an update. "
                    "Thank them for letting us handle this."
                )
            )
        elif next_step == "arrange self-pay":
            self.hangup(
                final_instructions=(
                    f"Let {first_name} know that our billing team will send them a statement "
                    f"for the balance of ${self.claim_amount}. "
                    "Let them know payment plan options may be available and they can discuss "
                    "those with our billing department. Provide the billing department number. "
                    "Thank them for their time."
                )
            )
        elif next_step == "I will contact my insurance company":
            self.hangup(
                final_instructions=(
                    f"Encourage {first_name} to contact their insurance company and reference "
                    f"claim number {self.claim_id}. Let them know our billing team is available "
                    "if they need documentation or additional information for the appeal. "
                    "Thank them for calling and wish them success with the appeal."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Let {first_name} know there's no rush and our billing team will follow "
                    "up with them by mail with their options in writing. "
                    "Reassure them that no immediate action is required right now. "
                    "Thank them for their time."
                )
            )

    def recipient_unavailable(self):
        logging.info(
            "Unable to reach %s for denial notification on claim %s",
            self.patient_name, self.claim_id,
        )
        self.hangup(
            final_instructions=(
                f"Leave a professional voicemail for {self.patient_name} from Riverside Family "
                "Medicine billing. Let them know this call is regarding an insurance claim "
                f"from {self.service_date} and ask them to call back at their earliest "
                "convenience. Provide the billing department callback number. "
                "Keep the message brief and professional — do not mention the word 'denial'."
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Outbound call to notify a patient of an insurance claim denial."
    )
    parser.add_argument("phone", help="Patient phone number (E.164, e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Patient full name")
    parser.add_argument("--claim-id", required=True, help="Waystar claim ID")
    parser.add_argument("--denial-reason", required=True, help="Denial reason description")
    parser.add_argument("--service", required=True, help="Service or procedure description")
    parser.add_argument("--service-date", required=True, help="Date of service (YYYY-MM-DD)")
    parser.add_argument("--amount", required=True, help="Claim amount (e.g. 350.00)")
    args = parser.parse_args()

    logging.info(
        "Initiating denial notification call to %s for claim %s",
        args.name, args.claim_id,
    )

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=DenialNotificationController(
            patient_name=args.name,
            claim_id=args.claim_id,
            denial_reason=args.denial_reason,
            service_description=args.service,
            service_date=args.service_date,
            claim_amount=args.amount,
        ),
    )
