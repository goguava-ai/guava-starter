import guava
import os
import logging
import json
import argparse
import requests
from datetime import datetime

logging.basicConfig(level=logging.INFO)

CALABRIO_BASE_URL = os.environ["CALABRIO_BASE_URL"]
CALABRIO_API_KEY = os.environ["CALABRIO_API_KEY"]

HEADERS = {
    "apiKey": CALABRIO_API_KEY,
    "Content-Type": "application/json",
    "Accept": "application/json",
}


def get_evaluation(evaluation_id: str) -> dict | None:
    """Fetches a quality evaluation from Calabrio by ID."""
    resp = requests.get(
        f"{CALABRIO_BASE_URL}/api/qualitymanagement/evaluations/{evaluation_id}",
        headers=HEADERS,
        timeout=10,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def schedule_coaching_session(
    agent_id: str,
    evaluation_id: str,
    preferred_date: str,
    agent_notes: str,
) -> dict:
    """Creates a coaching session in Calabrio linked to the evaluation."""
    payload = {
        "agentId": agent_id,
        "evaluationId": evaluation_id,
        "sessionType": "Coaching",
        "proposedDate": preferred_date,
        "notes": agent_notes,
        "status": "pending",
        "createdAt": datetime.utcnow().isoformat() + "Z",
    }
    resp = requests.post(
        f"{CALABRIO_BASE_URL}/api/qualitymanagement/coaching",
        headers=HEADERS,
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def update_evaluation_status(evaluation_id: str, agent_acknowledged: bool, notes: str) -> None:
    """Marks the evaluation as acknowledged by the agent."""
    requests.patch(
        f"{CALABRIO_BASE_URL}/api/qualitymanagement/evaluations/{evaluation_id}",
        headers=HEADERS,
        json={
            "agentAcknowledged": agent_acknowledged,
            "agentAcknowledgmentDate": datetime.utcnow().isoformat() + "Z",
            "agentNotes": notes,
        },
        timeout=10,
    )


class PostEvaluationCoachingController(guava.CallController):
    def __init__(self, agent_name: str, agent_id: str, evaluation_id: str, score: str, call_date: str):
        super().__init__()
        self.agent_name = agent_name
        self.agent_id = agent_id
        self.evaluation_id = evaluation_id
        self.score = score
        self.call_date = call_date

        self.set_persona(
            organization_name="Horizon Contact Center Quality Management",
            agent_name="Jordan",
            agent_purpose=(
                "to share quality evaluation feedback with agents and schedule coaching sessions"
            ),
        )

        self.reach_person(
            contact_full_name=self.agent_name,
            on_success=self.deliver_feedback,
            on_failure=self.recipient_unavailable,
        )

    def deliver_feedback(self):
        first_name = self.agent_name.split()[0] if self.agent_name else "there"

        self.set_task(
            objective=(
                f"Deliver quality evaluation results to {self.agent_name} for the call "
                f"on {self.call_date} (score: {self.score}). Gather their feedback and "
                "schedule a coaching session."
            ),
            checklist=[
                guava.Say(
                    f"Hi {first_name}, this is Jordan from Horizon Contact Center quality management. "
                    f"I'm reaching out about your quality evaluation for a call on {self.call_date}. "
                    f"Your overall score was {self.score}. I'd love to take a few minutes to share "
                    "some feedback and schedule a coaching session."
                ),
                guava.Field(
                    key="agent_reaction",
                    field_type="multiple_choice",
                    description=(
                        "Ask how they feel about their score and whether they'd like to discuss "
                        "specific areas for improvement."
                    ),
                    choices=[
                        "happy with the score",
                        "expected it to be higher",
                        "expected it to be lower",
                        "want to understand the scoring better",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="agent_self_assessment",
                    field_type="text",
                    description=(
                        "Ask: 'Is there anything specific about that call you felt went well "
                        "or could have gone better?' Capture their self-assessment."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="coaching_preference",
                    field_type="multiple_choice",
                    description="Ask when they would prefer to schedule the coaching session.",
                    choices=[
                        "this week",
                        "next week",
                        "within the next 30 days",
                        "I prefer async coaching via portal",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="coaching_time_preference",
                    field_type="text",
                    description=(
                        "Ask if they have a preferred time of day for coaching — morning, "
                        "afternoon, or end of shift. Optional."
                    ),
                    required=False,
                ),
            ],
            on_complete=self.schedule_coaching,
        )

    def schedule_coaching(self):
        reaction = self.get_field("agent_reaction")
        self_assessment = self.get_field("agent_self_assessment") or ""
        coaching_pref = self.get_field("coaching_preference")
        time_pref = self.get_field("coaching_time_preference") or ""
        first_name = self.agent_name.split()[0] if self.agent_name else "there"

        # Map preference to approximate date
        today = datetime.utcnow()
        date_map = {
            "this week": today.strftime("%Y-%m-%d"),
            "next week": (today.replace(day=today.day + 7)).strftime("%Y-%m-%d"),
            "within the next 30 days": (today.replace(day=today.day + 14)).strftime("%Y-%m-%d"),
        }
        proposed_date = date_map.get(coaching_pref, today.strftime("%Y-%m-%d"))

        agent_notes = f"Reaction: {reaction}."
        if self_assessment:
            agent_notes += f" Self-assessment: {self_assessment}"
        if time_pref:
            agent_notes += f" Preferred time: {time_pref}."

        logging.info(
            "Scheduling coaching for %s (eval %s) — preference: %s",
            self.agent_name, self.evaluation_id, coaching_pref,
        )

        # Acknowledge the evaluation
        try:
            update_evaluation_status(
                self.evaluation_id,
                agent_acknowledged=True,
                notes=self_assessment,
            )
            logging.info("Evaluation %s acknowledged", self.evaluation_id)
        except Exception as e:
            logging.warning("Failed to acknowledge evaluation: %s", e)

        if coaching_pref == "I prefer async coaching via portal":
            outcome = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "agent": "Jordan",
                "use_case": "post_evaluation_coaching",
                "agent_name": self.agent_name,
                "evaluation_id": self.evaluation_id,
                "score": self.score,
                "coaching_mode": "async_portal",
                "reaction": reaction,
            }
            print(json.dumps(outcome, indent=2))
            self.hangup(
                final_instructions=(
                    f"Let {first_name} know that's completely fine — we've noted their "
                    "preference and they'll receive coaching materials and feedback through "
                    "the Calabrio portal within two business days. Encourage them to reach "
                    "out if they have questions. Thank them for their time and continued dedication."
                )
            )
            return

        try:
            session = schedule_coaching_session(
                agent_id=self.agent_id,
                evaluation_id=self.evaluation_id,
                preferred_date=proposed_date,
                agent_notes=agent_notes,
            )
            session_id = session.get("id") or session.get("sessionId", "")
            logging.info("Coaching session created: %s", session_id)

            outcome = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "agent": "Jordan",
                "use_case": "post_evaluation_coaching",
                "agent_name": self.agent_name,
                "evaluation_id": self.evaluation_id,
                "score": self.score,
                "session_id": str(session_id),
                "proposed_date": proposed_date,
                "reaction": reaction,
                "self_assessment": self_assessment,
            }
            print(json.dumps(outcome, indent=2))

            self.hangup(
                final_instructions=(
                    f"Let {first_name} know that a coaching session has been scheduled "
                    f"based on their preference of '{coaching_pref}'. Their supervisor will "
                    "confirm the exact time and send a calendar invite. "
                    "Let them know coaching is a positive step and the team is invested in "
                    "their growth. Thank them for their openness and for taking the time to talk."
                )
            )
        except Exception as e:
            logging.error("Failed to schedule coaching session: %s", e)
            self.hangup(
                final_instructions=(
                    f"Apologize to {first_name} for a technical issue and let them know "
                    "their supervisor will be in touch to schedule the coaching session manually. "
                    "Thank them for their time and positive attitude."
                )
            )

    def recipient_unavailable(self):
        logging.info(
            "Unable to reach %s for evaluation %s coaching follow-up",
            self.agent_name, self.evaluation_id,
        )
        self.hangup(
            final_instructions=(
                f"Leave a brief, encouraging voicemail for {self.agent_name} from Horizon "
                "Contact Center quality management. Let them know you're calling about a "
                "recent quality evaluation and would like to connect to share feedback and "
                "schedule a coaching session. Ask them to call back or check the Calabrio "
                "portal. Keep the tone positive and supportive."
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Outbound coaching call following a Calabrio quality evaluation."
    )
    parser.add_argument("phone", help="Agent phone number (E.164, e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Agent full name")
    parser.add_argument("--agent-id", required=True, help="Calabrio agent ID")
    parser.add_argument("--evaluation-id", required=True, help="Calabrio evaluation ID")
    parser.add_argument("--score", required=True, help="Evaluation score (e.g. '82/100')")
    parser.add_argument("--call-date", required=True, help="Date of the evaluated call (YYYY-MM-DD)")
    args = parser.parse_args()

    logging.info(
        "Initiating post-evaluation coaching call to %s (eval %s, score %s)",
        args.name, args.evaluation_id, args.score,
    )

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=PostEvaluationCoachingController(
            agent_name=args.name,
            agent_id=args.agent_id,
            evaluation_id=args.evaluation_id,
            score=args.score,
            call_date=args.call_date,
        ),
    )
