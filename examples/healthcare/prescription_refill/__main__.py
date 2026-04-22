import guava
import os
import logging
from guava import logging_utils
import json
import argparse
from datetime import datetime



class PrescriptionRefillController(guava.CallController):
    def __init__(self, patient_name: str, medication: str):
        super().__init__()
        self.patient_name = patient_name
        self.medication = medication

        self.set_persona(
            organization_name="CareRx Pharmacy",
            agent_name="Riley",
            agent_purpose=(
                "to proactively notify patients when a prescription refill is due, confirm the refill, "
                "arrange a convenient pickup time, and connect patients with a pharmacist if they have questions"
            ),
        )

        self.reach_person(
            contact_full_name=self.patient_name,
            on_success=self.begin_refill_outreach,
            on_failure=self.recipient_unavailable,
        )

    def begin_refill_outreach(self):
        self.set_task(
            objective=(
                f"Notify {self.patient_name} that their prescription for {self.medication} is due for "
                "a refill at CareRx Pharmacy. Confirm whether they would like to proceed with the refill, "
                "collect a preferred pickup date if applicable, and note any questions they have for the "
                "pharmacist. If they request to speak with a pharmacist, capture that intent clearly."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.patient_name}, this is Riley calling from CareRx Pharmacy. "
                    f"I'm reaching out because your prescription for {self.medication} is coming up "
                    "for a refill, and we want to make sure you don't run out."
                ),
                guava.Say(
                    "I can go ahead and process the refill for you today, or if you have any questions "
                    "about your medication, I can arrange for a pharmacist to call you back."
                ),
                guava.Field(
                    key="refill_confirmed",
                    description=(
                        f"Ask the patient whether they would like to confirm the refill for {self.medication}, "
                        "decline it, or be connected with a pharmacist for questions. "
                        "Capture one of: 'yes', 'no', or 'call_pharmacist'."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="preferred_pickup_date",
                    description=(
                        "If the patient confirmed the refill, ask what date they would prefer to pick it up. "
                        "Only collect this if they said yes to the refill."
                    ),
                    field_type="date",
                    required=False,
                ),
                guava.Field(
                    key="questions_for_pharmacist",
                    description=(
                        "If the patient has questions or requested a pharmacist callback, ask them to briefly "
                        "describe what they would like to discuss. Only collect if relevant."
                    ),
                    field_type="text",
                    required=False,
                ),
            ],
            on_complete=self.save_results,
        )

    def save_results(self):
        results = {
            "timestamp": datetime.now().isoformat(),
            "patient_name": self.patient_name,
            "medication": self.medication,
            "refill_confirmed": self.get_field("refill_confirmed"),
            "preferred_pickup_date": self.get_field("preferred_pickup_date"),
            "questions_for_pharmacist": self.get_field("questions_for_pharmacist"),
        }
        print(json.dumps(results, indent=2))
        logging.info("Prescription refill results saved.")

        refill_status = self.get_field("refill_confirmed")
        if refill_status and str(refill_status).strip().lower() == "call_pharmacist":
            self.hangup(
                final_instructions=(
                    "Let the patient know that a CareRx pharmacist will give them a call back within "
                    "one business day to address their questions. Thank them for being a CareRx customer "
                    "and wish them good health."
                )
            )
        elif refill_status and str(refill_status).strip().lower() == "yes":
            pickup_date = self.get_field("preferred_pickup_date")
            pickup_msg = f"on {pickup_date}" if pickup_date else "at their convenience"
            self.hangup(
                final_instructions=(
                    f"Confirm to the patient that their refill for {self.medication} has been submitted "
                    f"and will be ready for pickup {pickup_msg} at CareRx Pharmacy. Let them know they "
                    "will receive a notification when it is ready. Thank them and wish them well."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    "Acknowledge the patient's decision and let them know they can call CareRx Pharmacy "
                    f"anytime to request a refill for {self.medication} when they are ready. "
                    "Thank them for their time and wish them good health."
                )
            )

    def recipient_unavailable(self):
        self.hangup(
            final_instructions=(
                "We were unable to reach the patient. Leave a brief, friendly voicemail on behalf of "
                f"CareRx Pharmacy letting them know their prescription for {self.medication} is due for "
                "a refill and asking them to call or visit the pharmacy at their convenience."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound prescription refill notification call for CareRx Pharmacy."
    )
    parser.add_argument("phone", help="Patient phone number to call")
    parser.add_argument("--name", required=True, help="Full name of the patient")
    parser.add_argument(
        "--medication",
        default="your prescription",
        help="Name of the medication due for refill (default: 'your prescription')",
    )
    args = parser.parse_args()

    logging.info(
        "Initiating prescription refill call to %s (%s) for medication: %s",
        args.name,
        args.phone,
        args.medication,
    )

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=PrescriptionRefillController(
            patient_name=args.name,
            medication=args.medication,
        ),
    )
