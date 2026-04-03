import guava
import os
import logging
import requests
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)


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


def get_view_by_name(view_name: str) -> dict | None:
    """Searches for a Tableau view by name. Returns the first match or None."""
    resp = requests.get(
        f"{API_BASE}/views",
        headers=HEADERS,
        params={"filter": f"name:eq:{view_name}"},
        timeout=10,
    )
    resp.raise_for_status()
    views = resp.json().get("views", {}).get("view", [])
    return views[0] if views else None


class ViewStatusCheckController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Vertex Analytics",
            agent_name="Jordan",
            agent_purpose=(
                "to help callers check whether a specific Tableau view is up to date and available"
            ),
        )

        self.set_task(
            objective=(
                "A caller wants to know if a particular Tableau view is fresh and accessible. "
                "Collect the view name, look it up, and report its status including when it was "
                "last updated and whether it's current."
            ),
            checklist=[
                guava.Say(
                    "Thanks for calling Vertex Analytics. This is Jordan. "
                    "I can check the status of any Tableau view for you — "
                    "just let me know which one you'd like to look up."
                ),
                guava.Field(
                    key="view_name",
                    field_type="text",
                    description="Ask the caller for the exact name of the Tableau view they want to check.",
                    required=True,
                ),
                guava.Field(
                    key="site_content_url",
                    field_type="text",
                    description=(
                        "Ask if the view lives on a different Tableau site than the default. "
                        "If they're unsure or it's the same site, skip this."
                    ),
                    required=False,
                ),
            ],
            on_complete=self.check_view_status,
        )

        self.accept_call()

    def check_view_status(self):
        view_name = self.get_field("view_name") or ""

        logging.info("Looking up Tableau view: %s", view_name)
        try:
            view = get_view_by_name(view_name)
        except Exception as e:
            logging.error("View lookup failed: %s", e)
            view = None

        if not view:
            self.hangup(
                final_instructions=(
                    f"Let the caller know you couldn't find a Tableau view named '{view_name}'. "
                    "Suggest they double-check the name and try again. Be helpful and apologetic."
                )
            )
            return

        name = view.get("name", view_name)
        updated_at_str = view.get("updatedAt", "")
        owner = view.get("owner", {}).get("name", "unknown")

        is_current = False
        updated_display = "unknown"

        if updated_at_str:
            try:
                # Tableau returns ISO 8601 timestamps like "2024-03-15T10:30:00Z"
                updated_at = datetime.fromisoformat(updated_at_str.replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                age_hours = (now - updated_at).total_seconds() / 3600
                is_current = age_hours <= 24
                updated_display = updated_at.strftime("%B %d, %Y at %I:%M %p UTC")
            except Exception as e:
                logging.warning("Could not parse updatedAt '%s': %s", updated_at_str, e)

        freshness = "current (updated within the last 24 hours)" if is_current else "out of date (last updated more than 24 hours ago)"

        logging.info(
            "View '%s' last updated: %s, current: %s", name, updated_display, is_current
        )

        self.hangup(
            final_instructions=(
                f"Report the following Tableau view status to the caller in a clear, friendly way. "
                f"View name: {name}. Last updated: {updated_display}. "
                f"Freshness: {freshness}. Owner: {owner}. "
                "If the view is out of date, let them know they may want to contact their "
                "Tableau administrator to trigger a refresh. Thank them for calling Vertex Analytics."
            )
        )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=ViewStatusCheckController,
    )
