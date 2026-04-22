import guava
import os
import logging
from guava import logging_utils
import argparse
import requests


TENANT_ID = os.environ["POWERBI_TENANT_ID"]
CLIENT_ID = os.environ["POWERBI_CLIENT_ID"]
CLIENT_SECRET = os.environ["POWERBI_CLIENT_SECRET"]
WORKSPACE_ID = os.environ["POWERBI_WORKSPACE_ID"]

BASE_URL = "https://api.powerbi.com/v1.0/myorg"


def get_access_token() -> str:
    resp = requests.post(
        f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token",
        data={
            "grant_type": "client_credentials",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "scope": "https://analysis.windows.net/powerbi/api/.default",
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def trigger_dataset_refresh(dataset_id: str, token: str) -> None:
    """Trigger an on-demand refresh for the specified dataset."""
    resp = requests.post(
        f"{BASE_URL}/groups/{WORKSPACE_ID}/datasets/{dataset_id}/refreshes",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    resp.raise_for_status()


def get_dataset_info(dataset_id: str, token: str) -> dict:
    resp = requests.get(
        f"{BASE_URL}/groups/{WORKSPACE_ID}/datasets/{dataset_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def get_last_refresh(dataset_id: str, token: str) -> dict | None:
    resp = requests.get(
        f"{BASE_URL}/groups/{WORKSPACE_ID}/datasets/{dataset_id}/refreshes",
        headers={"Authorization": f"Bearer {token}"},
        params={"$top": 1},
        timeout=10,
    )
    resp.raise_for_status()
    items = resp.json().get("value", [])
    return items[0] if items else None


class DatasetRefreshTriggerController(guava.CallController):
    def __init__(self, contact_name: str, dataset_id: str, dataset_name: str):
        super().__init__()
        self.contact_name = contact_name
        self.dataset_id = dataset_id
        self.dataset_name = dataset_name
        self._token: str = ""
        self._last_refresh_time: str = ""

        try:
            self._token = get_access_token()
            last = get_last_refresh(dataset_id, self._token)
            if last:
                self._last_refresh_time = last.get("endTime") or last.get("startTime") or ""
        except Exception as e:
            logging.warning("Pre-call Power BI setup failed: %s", e)

        self.set_persona(
            organization_name="Apex Analytics",
            agent_name="Morgan",
            agent_purpose=(
                "to coordinate Power BI dataset refreshes with data owners "
                "and confirm that data is up to date"
            ),
        )

        self.reach_person(
            contact_full_name=contact_name,
            on_success=self.request_confirmation,
            on_failure=self.recipient_unavailable,
        )

    def request_confirmation(self):
        last_note = (
            f" It last completed a refresh at {self._last_refresh_time}."
            if self._last_refresh_time
            else ""
        )

        self.set_task(
            objective=(
                f"Confirm with {self.contact_name} that it's safe to trigger an on-demand "
                f"refresh of the '{self.dataset_name}' Power BI dataset."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.contact_name}, this is Morgan from Apex Analytics. "
                    f"I'm calling because we'd like to trigger a manual refresh of "
                    f"the '{self.dataset_name}' dataset in Power BI.{last_note} "
                    "I just want to confirm this is a good time before we kick it off."
                ),
                guava.Field(
                    key="approval",
                    field_type="multiple_choice",
                    description=(
                        "Ask if they approve triggering the dataset refresh now, or "
                        "if there's a reason to wait."
                    ),
                    choices=[
                        "yes, go ahead",
                        "wait — I'm currently editing the dataset",
                        "no — not needed right now",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="notes",
                    field_type="text",
                    description=(
                        "Ask if there's anything we should know before triggering — "
                        "for example, whether the source data has been fully loaded."
                    ),
                    required=False,
                ),
            ],
            on_complete=self.handle_approval,
        )

    def handle_approval(self):
        approval = self.get_field("approval") or "yes, go ahead"
        notes = self.get_field("notes") or ""

        logging.info(
            "Refresh approval for dataset %s: %s (notes: %s)",
            self.dataset_id, approval, notes,
        )

        if approval != "yes, go ahead":
            self.hangup(
                final_instructions=(
                    f"Thank {self.contact_name} for the heads-up. Let them know you'll hold off "
                    "on the refresh and check back with them later. If they indicated they're editing "
                    "the dataset, let them know you'll try again once they've confirmed it's ready."
                )
            )
            return

        try:
            if not self._token:
                self._token = get_access_token()
            trigger_dataset_refresh(self.dataset_id, self._token)
            logging.info("Power BI dataset refresh triggered: %s", self.dataset_id)
            self.hangup(
                final_instructions=(
                    f"Let {self.contact_name} know the refresh has been triggered successfully. "
                    f"Depending on the dataset size, it may take a few minutes to complete. "
                    "They'll be able to see the refresh status in Power BI. "
                    "Thank them for their time."
                )
            )
        except Exception as e:
            logging.error("Failed to trigger Power BI refresh: %s", e)
            self.hangup(
                final_instructions=(
                    f"Apologize to {self.contact_name} — the refresh trigger encountered a technical issue. "
                    "Let them know our team will investigate and try again shortly."
                )
            )

    def recipient_unavailable(self):
        logging.info("Unable to reach %s for dataset refresh confirmation", self.contact_name)
        self.hangup(
            final_instructions=(
                f"Leave a brief voicemail for {self.contact_name} from Apex Analytics. "
                f"Let them know you were calling to confirm a manual refresh of '{self.dataset_name}' "
                "in Power BI and that you'll send a follow-up email."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound call to confirm and trigger a Power BI dataset refresh."
    )
    parser.add_argument("phone", help="Contact phone number (E.164)")
    parser.add_argument("--name", required=True, help="Contact full name")
    parser.add_argument("--dataset-id", required=True, help="Power BI dataset ID (GUID)")
    parser.add_argument("--dataset-name", required=True, help="Human-readable dataset name")
    args = parser.parse_args()

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=DatasetRefreshTriggerController(
            contact_name=args.name,
            dataset_id=args.dataset_id,
            dataset_name=args.dataset_name,
        ),
    )
