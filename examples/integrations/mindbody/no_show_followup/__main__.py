import guava
import os
import logging
from guava import logging_utils
import json
import argparse
import requests
from datetime import datetime, timezone


BASE_URL = "https://api.mindbodyonline.com/public/v6"
API_KEY = os.environ["MINDBODY_API_KEY"]
SITE_ID = os.environ["MINDBODY_SITE_ID"]


def get_headers(user_token: str | None = None) -> dict:
    headers = {
        "Api-Key": API_KEY,
        "SiteId": SITE_ID,
        "Content-Type": "application/json",
    }
    if user_token:
        headers["Authorization"] = f"Bearer {user_token}"
    return headers


def get_staff_token() -> str:
    """Obtain a staff user token for API operations that require authentication."""
    resp = requests.post(
        f"{BASE_URL}/usertoken/issue",
        headers={"Api-Key": API_KEY, "SiteId": SITE_ID, "Content-Type": "application/json"},
        json={
            "Username": os.environ["MINDBODY_STAFF_USERNAME"],
            "Password": os.environ["MINDBODY_STAFF_PASSWORD"],
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["AccessToken"]


class NoShowFollowupController(guava.CallController):
    def __init__(
        self,
        client_name: str,
        client_id: str,
        class_name: str,
        class_date: str,
    ):
        super().__init__()
        self.client_name = client_name
        self.client_id = client_id
        self.class_name = class_name
        self.class_date = class_date

        self.set_persona(
            organization_name="FlexFit Studio",
            agent_name="Riley",
            agent_purpose="to check in with FlexFit Studio members who missed a class and help re-engage them",
        )

        self.reach_person(
            contact_full_name=self.client_name,
            on_success=self.begin_followup,
            on_failure=self.leave_voicemail,
        )

    def begin_followup(self):
        self.set_task(
            objective=(
                f"Follow up with {self.client_name} from FlexFit Studio about their missed "
                f"{self.class_name} class on {self.class_date}. Check in warmly, find out why "
                "they couldn't make it, and see if they'd like to rebook."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.client_name}! This is Riley calling from FlexFit Studio. "
                    f"We noticed you weren't able to make it to {self.class_name} on {self.class_date} "
                    "and just wanted to check in — we missed you!"
                ),
                guava.Field(
                    key="miss_reason",
                    field_type="multiple_choice",
                    description=(
                        "Ask if everything is okay and why they weren't able to make it to class. "
                        "Map their answer to the closest option — keep the tone warm and non-judgmental."
                    ),
                    choices=["yes, just forgot", "had an emergency", "no longer interested in this class type"],
                    required=True,
                ),
                guava.Field(
                    key="want_to_rebook",
                    field_type="multiple_choice",
                    description=(
                        "Ask if they'd like to get back on the schedule and come to another class. "
                        "Map their answer to 'yes please' or 'no thanks'."
                    ),
                    choices=["yes please", "no thanks"],
                    required=True,
                ),
            ],
            on_complete=self.save_results,
        )

    def save_results(self):
        miss_reason = self.get_field("miss_reason")
        want_to_rebook = self.get_field("want_to_rebook")

        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": "Riley",
            "organization": "FlexFit Studio",
            "use_case": "no_show_followup",
            "client_id": self.client_id,
            "client_name": self.client_name,
            "class_name": self.class_name,
            "class_date": self.class_date,
            "fields": {
                "miss_reason": miss_reason,
                "want_to_rebook": want_to_rebook,
            },
        }
        print(json.dumps(results, indent=2))
        logging.info("No-show follow-up result saved for client %s.", self.client_id)

        # Log the no-show interaction note back to Mindbody as a client visit note
        # by fetching a staff token and using the client notes endpoint (best-effort).
        try:
            token = get_staff_token()
            note_body = (
                f"No-show follow-up call on {datetime.now().date().isoformat()}. "
                f"Missed: {self.class_name} on {self.class_date}. "
                f"Reason: {miss_reason}. "
                f"Wants to rebook: {want_to_rebook}."
            )
            requests.post(
                f"{BASE_URL}/client/addclientformulae",
                headers=get_headers(token),
                json={
                    "ClientId": self.client_id,
                    "Note": note_body,
                },
                timeout=10,
            )
            logging.info("Logged no-show note to Mindbody for client %s.", self.client_id)
        except Exception as e:
            # Non-critical — the call results are already printed above.
            logging.warning("Could not log note to Mindbody: %s", e)

        if want_to_rebook == "yes please":
            encouragement = (
                "amazing" if miss_reason == "had an emergency" else "great"
            )
            self.hangup(
                final_instructions=(
                    f"Tell {self.client_name} that's {encouragement} to hear — we'd love to have "
                    f"them back! Let them know they can call FlexFit Studio anytime to book their "
                    f"next {self.class_name} class, or they can grab a spot online at "
                    "flexfitstudio.com. Encourage them and let them know the whole team is looking "
                    "forward to seeing them. Thank them for their time and wish them a wonderful day."
                )
            )
        else:
            # Not interested in this class type — find out what might work better.
            self.set_task(
                objective=(
                    f"Since {self.client_name} isn't interested in rebooking {self.class_name}, "
                    "find out what type of class might be a better fit and encourage them to stay engaged."
                ),
                checklist=[
                    guava.Field(
                        key="preferred_class_type",
                        field_type="multiple_choice",
                        description=(
                            "Ask what type of class they might enjoy more or feel motivated to try. "
                            "Map their answer to the closest option."
                        ),
                        choices=["yoga", "spin", "HIIT", "pilates", "barre", "boxing"],
                        required=True,
                    ),
                ],
                on_complete=self.wrap_up_alternate_interest,
            )

    def wrap_up_alternate_interest(self):
        preferred = self.get_field("preferred_class_type")

        # Update results log with the additional preference.
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": "Riley",
            "organization": "FlexFit Studio",
            "use_case": "no_show_followup",
            "client_id": self.client_id,
            "client_name": self.client_name,
            "phase": "alternate_interest",
            "fields": {
                "preferred_class_type": preferred,
            },
        }
        print(json.dumps(results, indent=2))
        logging.info(
            "Recorded alternate class interest '%s' for client %s.", preferred, self.client_id
        )

        self.hangup(
            final_instructions=(
                f"Thank {self.client_name} for sharing that — let them know you've noted their "
                f"interest in {preferred} and the team will keep that in mind. "
                f"Encourage them warmly: FlexFit Studio has a fantastic {preferred} program and "
                "you'd love to see them give it a try. Let them know they're always welcome "
                "and we're rooting for them. Thank them and wish them a great rest of the day."
            )
        )

    def leave_voicemail(self):
        self.hangup(
            final_instructions=(
                f"Leave a friendly voicemail for {self.client_name} on behalf of FlexFit Studio. "
                f"Mention that we noticed they missed {self.class_name} on {self.class_date} "
                "and just wanted to check in — no worries at all! Let them know we'd love to "
                "see them back on the schedule whenever they're ready, and they can call us or "
                "book online at flexfitstudio.com. Keep the tone warm, upbeat, and pressure-free. "
                "Thank them and look forward to seeing them soon."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound no-show follow-up call for FlexFit Studio via Mindbody."
    )
    parser.add_argument(
        "phone",
        help="Member phone number to call (E.164 format, e.g. +15551234567)",
    )
    parser.add_argument("--name", required=True, help="Full name of the member")
    parser.add_argument("--client-id", required=True, help="Mindbody client ID")
    parser.add_argument("--class-name", required=True, help="Name of the class they missed (e.g. 'Tuesday Morning Yoga')")
    parser.add_argument("--class-date", required=True, help="Date/time of the missed class (e.g. 'Tuesday, March 25 at 7:00 AM')")
    args = parser.parse_args()

    logging.info(
        "Initiating no-show follow-up call to %s (%s), client ID: %s, missed: %s on %s",
        args.name,
        args.phone,
        args.client_id,
        args.class_name,
        args.class_date,
    )

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=NoShowFollowupController(
            client_name=args.name,
            client_id=args.client_id,
            class_name=args.class_name,
            class_date=args.class_date,
        ),
    )
