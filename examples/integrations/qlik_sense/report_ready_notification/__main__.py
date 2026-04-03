import guava
import os
import logging
import argparse
import requests

logging.basicConfig(level=logging.INFO)

QLIK_TENANT_URL = os.environ["QLIK_TENANT_URL"].rstrip("/")
QLIK_API_KEY = os.environ["QLIK_API_KEY"]

HEADERS = {
    "Authorization": f"Bearer {QLIK_API_KEY}",
    "Content-Type": "application/json",
}


def get_reload_details(reload_id: str) -> dict | None:
    resp = requests.get(
        f"{QLIK_TENANT_URL}/api/v1/reloads/{reload_id}",
        headers=HEADERS,
        timeout=10,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def get_app_details(app_id: str) -> dict | None:
    resp = requests.get(
        f"{QLIK_TENANT_URL}/api/v1/apps/{app_id}",
        headers=HEADERS,
        timeout=10,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


class ReportReadyNotificationController(guava.CallController):
    def __init__(
        self,
        recipient_name: str,
        app_name: str,
        app_id: str,
        reload_id: str,
        reload_duration_minutes: str,
    ):
        super().__init__()
        self.recipient_name = recipient_name
        self.app_name = app_name
        self.app_id = app_id
        self.reload_id = reload_id
        self.reload_duration_minutes = reload_duration_minutes

        self.set_persona(
            organization_name="Apex Analytics",
            agent_name="Casey",
            agent_purpose=(
                "to notify Apex Analytics stakeholders when their Qlik reports have "
                "finished reloading and are ready to view"
            ),
        )

        self.reach_person(
            contact_full_name=recipient_name,
            on_success=self.deliver_notification,
            on_failure=self.recipient_unavailable,
        )

    def deliver_notification(self):
        app_url = f"{QLIK_TENANT_URL}/sense/app/{self.app_id}"
        duration_note = (
            f" The reload completed in {self.reload_duration_minutes} minutes."
            if self.reload_duration_minutes
            else ""
        )

        self.set_task(
            objective=(
                f"Notify {self.recipient_name} that the '{self.app_name}' Qlik app has "
                "finished reloading and is ready for review."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.recipient_name}! This is Casey from Apex Analytics. "
                    f"I'm calling to let you know that your Qlik report, '{self.app_name}', "
                    f"has finished reloading and is ready to view.{duration_note} "
                    "The data is fresh as of right now."
                ),
                guava.Field(
                    key="feedback",
                    field_type="multiple_choice",
                    description=(
                        "Ask if they have any questions about the reload or if there's "
                        "anything specific they'd like the analytics team to check."
                    ),
                    choices=[
                        "no, I'll check it now",
                        "yes, I have a question for the team",
                        "please send me the link by email",
                    ],
                    required=True,
                ),
            ],
            on_complete=lambda: self.close_notification(app_url),
        )

    def close_notification(self, app_url: str):
        feedback = self.get_field("feedback") or "no, I'll check it now"

        logging.info(
            "Report-ready notification delivered to %s for app '%s': %s",
            self.recipient_name, self.app_name, feedback,
        )

        if "question" in feedback:
            self.hangup(
                final_instructions=(
                    f"Let {self.recipient_name} know the analytics team will follow up "
                    "by email to address their question. Thank them for flagging it. "
                    "Remind them the report is live and ready at their convenience."
                )
            )
        elif "email" in feedback:
            self.hangup(
                final_instructions=(
                    f"Let {self.recipient_name} know you'll have the analytics team send them "
                    f"a direct link to the report by email. The app is '{self.app_name}'. "
                    "Thank them and wish them a good day."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Wish {self.recipient_name} a great review session. "
                    f"Let them know the link is available at {app_url} if they need it. "
                    "Thank them for their time."
                )
            )

    def recipient_unavailable(self):
        logging.info(
            "Unable to reach %s for report-ready notification on app %s",
            self.recipient_name, self.app_name,
        )
        self.hangup(
            final_instructions=(
                f"Leave a brief, upbeat voicemail for {self.recipient_name} from Apex Analytics. "
                f"Let them know the '{self.app_name}' Qlik report has finished reloading "
                "and is ready to view. Keep it under 15 seconds."
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Outbound notification call when a Qlik app reload completes."
    )
    parser.add_argument("phone", help="Recipient phone number (E.164)")
    parser.add_argument("--name", required=True, help="Recipient full name")
    parser.add_argument("--app-name", required=True, help="Qlik app name")
    parser.add_argument("--app-id", required=True, help="Qlik app ID")
    parser.add_argument("--reload-id", default="", help="Reload job ID")
    parser.add_argument("--duration", default="", help="Reload duration in minutes")
    args = parser.parse_args()

    logging.info("Notifying %s (%s) — Qlik app '%s' is ready", args.name, args.phone, args.app_name)

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=ReportReadyNotificationController(
            recipient_name=args.name,
            app_name=args.app_name,
            app_id=args.app_id,
            reload_id=args.reload_id,
            reload_duration_minutes=args.duration,
        ),
    )
