import guava
import os
import logging
from guava import logging_utils
import argparse
import requests
from datetime import datetime, timezone



def _signin() -> tuple[str, str]:
    resp = requests.post(
        f"{os.environ['TABLEAU_SERVER_URL']}/api/3.21/auth/signin",
        json={
            "credentials": {
                "personalAccessTokenName": os.environ["TABLEAU_PAT_NAME"],
                "personalAccessTokenSecret": os.environ["TABLEAU_PAT_SECRET"],
                "site": {"contentUrl": os.environ["TABLEAU_SITE_NAME"]},
            }
        },
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        timeout=15,
    )
    resp.raise_for_status()
    creds = resp.json()["credentials"]
    return creds["token"], creds["site"]["id"]


_TOKEN, _SITE_ID = _signin()
SERVER_URL = os.environ["TABLEAU_SERVER_URL"]
HEADERS = {"X-Tableau-Auth": _TOKEN, "Content-Type": "application/json", "Accept": "application/json"}
API_BASE = f"{SERVER_URL}/api/3.21/sites/{_SITE_ID}"


def get_workbook(workbook_id: str) -> dict:
    """Fetches workbook metadata by ID."""
    resp = requests.get(
        f"{API_BASE}/workbooks/{workbook_id}",
        headers=HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("workbook", {})


class WorkbookRefreshNotifyController(guava.CallController):
    def __init__(self, workbook_id: str, contact_name: str, refresh_status: str):
        super().__init__()
        self.workbook_id = workbook_id
        self.contact_name = contact_name
        self.refresh_status = refresh_status  # "completed" or "failed"

        # Fetch workbook details before the call
        self.workbook_name = "your workbook"
        self.updated_display = "recently"
        self.size_display = ""

        try:
            workbook = get_workbook(workbook_id)
            self.workbook_name = workbook.get("name", self.workbook_name)
            updated_at_str = workbook.get("updatedAt", "")
            if updated_at_str:
                updated_at = datetime.fromisoformat(updated_at_str.replace("Z", "+00:00"))
                self.updated_display = updated_at.strftime("%B %d, %Y at %I:%M %p UTC")
            size_bytes = workbook.get("size")
            if size_bytes is not None:
                size_mb = int(size_bytes) / (1024 * 1024)
                self.size_display = f"{size_mb:.1f} MB"
        except Exception as e:
            logging.error("Failed to fetch workbook %s pre-call: %s", workbook_id, e)

        self.set_persona(
            organization_name="Vertex Analytics",
            agent_name="Alex",
            agent_purpose=(
                "to notify users when their Tableau workbook refresh has completed or failed "
                "and capture any follow-up actions they need"
            ),
        )

        self.reach_person(
            contact_full_name=contact_name,
            on_success=self.deliver_notification,
            on_failure=self.recipient_unavailable,
        )

    def deliver_notification(self):
        if self.refresh_status == "completed":
            status_message = (
                f"I'm calling to let you know that the refresh for your Tableau workbook "
                f"'{self.workbook_name}' has completed successfully. "
                f"It was last updated on {self.updated_display}."
            )
            if self.size_display:
                status_message += f" The workbook is currently {self.size_display}."
        else:
            status_message = (
                f"I'm calling to let you know that the refresh for your Tableau workbook "
                f"'{self.workbook_name}' has unfortunately failed. "
                "Our team has been notified, but I wanted to make sure you were aware directly."
            )

        self.set_task(
            objective=(
                f"Notify {self.contact_name} about the Tableau workbook refresh "
                f"{'completion' if self.refresh_status == 'completed' else 'failure'} "
                f"for '{self.workbook_name}'. Capture their reaction and any issues they've noticed."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.contact_name}, this is Alex from Vertex Analytics. "
                    + status_message
                ),
                guava.Field(
                    key="satisfaction",
                    field_type="multiple_choice",
                    description=(
                        "Ask the user how they'd characterize the situation — are they satisfied "
                        "with the refresh outcome, do they need someone to review it, or will "
                        "they check the workbook themselves?"
                    ),
                    choices=["satisfied", "needs-review", "will-check-myself"],
                    required=True,
                ),
                guava.Field(
                    key="any_issues",
                    field_type="text",
                    description=(
                        "Ask if they've noticed any data issues or discrepancies in the workbook "
                        "that they'd like the analytics team to look into. "
                        "Skip if they're satisfied and have no concerns."
                    ),
                    required=False,
                ),
            ],
            on_complete=self.record_outcome,
        )

    def record_outcome(self):
        satisfaction = self.get_field("satisfaction") or "satisfied"
        any_issues = self.get_field("any_issues") or ""

        logging.info(
            "Refresh notification outcome for workbook %s — status: %s, satisfaction: %s",
            self.workbook_id, self.refresh_status, satisfaction,
        )
        if any_issues:
            logging.info("Issues reported: %s", any_issues)

        if satisfaction == "needs-review":
            issue_note = f" They noted: {any_issues}." if any_issues else ""
            self.hangup(
                final_instructions=(
                    f"Let {self.contact_name} know the analytics team will review the workbook "
                    f"'{self.workbook_name}' and follow up with them shortly.{issue_note} "
                    "Thank them for flagging it and wish them a great day."
                )
            )
        elif satisfaction == "will-check-myself":
            self.hangup(
                final_instructions=(
                    f"Acknowledge that {self.contact_name} will check the workbook themselves. "
                    "Let them know the analytics team is available if they have any questions "
                    "after reviewing. Wish them a great day."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Thank {self.contact_name} for their time. "
                    "Let them know the analytics team is here if anything comes up. "
                    "Wish them a great day."
                )
            )

    def recipient_unavailable(self):
        logging.info(
            "Unable to reach %s for workbook refresh notification on workbook %s",
            self.contact_name, self.workbook_id,
        )
        status_word = "completed" if self.refresh_status == "completed" else "encountered an issue"
        self.hangup(
            final_instructions=(
                f"Leave a brief voicemail for {self.contact_name} on behalf of Vertex Analytics. "
                f"Let them know the refresh for the Tableau workbook '{self.workbook_name}' has "
                f"{status_word} and ask them to reach out to the analytics team if they have "
                "any questions. Keep it concise and professional."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound call to notify a user of a Tableau workbook refresh result."
    )
    parser.add_argument("phone", help="User phone number (E.164, e.g. +15551234567)")
    parser.add_argument("--workbook-id", required=True, help="Tableau workbook ID")
    parser.add_argument("--name", required=True, help="User's full name")
    parser.add_argument(
        "--status",
        required=True,
        choices=["completed", "failed"],
        help="Refresh status to report to the user",
    )
    args = parser.parse_args()

    logging.info(
        "Initiating workbook refresh notification to %s (%s) for workbook %s (status: %s)",
        args.name, args.phone, args.workbook_id, args.status,
    )

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=WorkbookRefreshNotifyController(
            workbook_id=args.workbook_id,
            contact_name=args.name,
            refresh_status=args.status,
        ),
    )
