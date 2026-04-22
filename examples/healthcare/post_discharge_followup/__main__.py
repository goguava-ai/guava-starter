import guava
import os
import logging
from guava import logging_utils
import json
import argparse
from datetime import datetime



class PostDischargeFollowupController(guava.CallController):
    def __init__(self, patient_name: str):
        super().__init__()
        self.patient_name = patient_name

        self.set_persona(
            organization_name="Riverside Medical Center",
            agent_name="Sam",
            agent_purpose=(
                "to follow up with recently discharged patients, check on their recovery progress, "
                "confirm medication adherence, and identify any concerns that require clinical attention"
            ),
        )

        self.reach_person(
            contact_full_name=self.patient_name,
            on_success=self.begin_followup,
            on_failure=self.recipient_unavailable,
        )

    def begin_followup(self):
        self.set_task(
            objective=(
                f"Conduct a post-discharge follow-up call with {self.patient_name} on behalf of "
                "Riverside Medical Center. Assess their recovery status, confirm they are taking "
                "medications as prescribed, gauge their current pain level, identify any concerning "
                "symptoms, and determine whether a follow-up appointment is needed. Flag any urgent "
                "concerns for immediate clinical review."
            ),
            checklist=[
                guava.Say(
                    f"Hello {self.patient_name}, this is Sam calling from Riverside Medical Center. "
                    "We're following up to see how you're feeling since your recent discharge and to "
                    "make sure your recovery is going smoothly."
                ),
                guava.Field(
                    key="recovery_status",
                    description=(
                        "Ask the patient how their overall recovery is going. Capture a brief "
                        "description of how they are feeling in their own words (e.g., 'doing well', "
                        "'tired but improving', 'struggling')."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="medications_taken_as_prescribed",
                    description=(
                        "Ask whether the patient has been taking all medications exactly as prescribed "
                        "by their care team since discharge. Capture their response (e.g., 'yes', 'no', "
                        "'missed a few doses')."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="pain_level",
                    description=(
                        "Ask the patient to rate their current pain level on a scale from 0 to 10, "
                        "where 0 is no pain and 10 is the worst pain imaginable."
                    ),
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="concerning_symptoms",
                    description=(
                        "Ask if the patient has experienced any concerning or unexpected symptoms since "
                        "discharge, such as fever, unusual swelling, difficulty breathing, or wound "
                        "changes. Capture any symptoms they describe. Skip if they have none."
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="needs_followup_appointment",
                    description=(
                        "Based on the conversation, ask whether the patient feels they need a follow-up "
                        "appointment with their care team. Capture their response (e.g., 'yes', 'no', "
                        "'unsure')."
                    ),
                    field_type="text",
                    required=True,
                ),
            ],
            on_complete=self.save_results,
        )

    def save_results(self):
        results = {
            "timestamp": datetime.now().isoformat(),
            "patient_name": self.patient_name,
            "recovery_status": self.get_field("recovery_status"),
            "medications_taken_as_prescribed": self.get_field("medications_taken_as_prescribed"),
            "pain_level": self.get_field("pain_level"),
            "concerning_symptoms": self.get_field("concerning_symptoms"),
            "needs_followup_appointment": self.get_field("needs_followup_appointment"),
        }
        print(json.dumps(results, indent=2))
        logging.info("Post-discharge follow-up results saved.")

        pain_level = self.get_field("pain_level")
        concerning_symptoms = self.get_field("concerning_symptoms")
        high_pain = isinstance(pain_level, int) and pain_level >= 7
        has_symptoms = concerning_symptoms and str(concerning_symptoms).strip()

        if high_pain or has_symptoms:
            self.hangup(
                final_instructions=(
                    "Express genuine concern for the patient's wellbeing. Let them know that based on "
                    "what they shared, you will flag their information for urgent review by a clinical "
                    "team member who will reach out to them shortly. Advise them to call 911 or go to "
                    "the nearest emergency room if their condition worsens before then. Thank them for "
                    "their time and wish them a speedy recovery."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    "Thank the patient for taking the time to speak with you. Let them know their "
                    "responses have been recorded and the care team at Riverside Medical Center will "
                    "review them. Remind them they can call the clinic at any time if they have "
                    "questions or concerns. Wish them a continued smooth recovery."
                )
            )

    def recipient_unavailable(self):
        self.hangup(
            final_instructions=(
                "We were unable to reach the patient. Leave a caring voicemail on behalf of "
                "Riverside Medical Center letting them know we called to check on their recovery "
                "and asking them to call us back at their earliest convenience. Provide the "
                "clinic's main number if available."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound post-discharge follow-up call for Riverside Medical Center."
    )
    parser.add_argument("phone", help="Patient phone number to call")
    parser.add_argument("--name", required=True, help="Full name of the patient")
    args = parser.parse_args()

    logging.info(
        "Initiating post-discharge follow-up call to %s (%s)",
        args.name,
        args.phone,
    )

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=PostDischargeFollowupController(
            patient_name=args.name,
        ),
    )
