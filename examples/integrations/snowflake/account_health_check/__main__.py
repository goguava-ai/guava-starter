import guava
import os
import logging
import requests

logging.basicConfig(level=logging.INFO)

SNOWFLAKE_ACCOUNT = os.environ["SNOWFLAKE_ACCOUNT"]
SNOWFLAKE_JWT_TOKEN = os.environ["SNOWFLAKE_JWT_TOKEN"]
SNOWFLAKE_WAREHOUSE = os.environ["SNOWFLAKE_WAREHOUSE"]
SNOWFLAKE_DATABASE = os.environ["SNOWFLAKE_DATABASE"]
SNOWFLAKE_SCHEMA = os.environ["SNOWFLAKE_SCHEMA"]
SNOWFLAKE_ROLE = os.environ["SNOWFLAKE_ROLE"]

HEADERS = {
    "Authorization": f"Bearer {SNOWFLAKE_JWT_TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json",
    "X-Snowflake-Authorization-Token-Type": "KEYPAIR_JWT",
}
BASE_URL = f"https://{SNOWFLAKE_ACCOUNT}.snowflakecomputing.com/api/v2"


def execute_statement(statement: str, bindings: dict | None = None) -> dict:
    """Executes a SQL statement against Snowflake and returns the raw response."""
    payload = {
        "statement": statement,
        "database": SNOWFLAKE_DATABASE,
        "schema": SNOWFLAKE_SCHEMA,
        "warehouse": SNOWFLAKE_WAREHOUSE,
        "role": SNOWFLAKE_ROLE,
        "timeout": 60,
    }
    if bindings:
        payload["bindings"] = bindings
    resp = requests.post(f"{BASE_URL}/statements", headers=HEADERS, json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json()


def parse_results(response: dict) -> list[dict]:
    """Zips column names with each row and returns a list of row dicts."""
    row_types = response.get("resultSetMetaData", {}).get("rowType", [])
    col_names = [col["name"] for col in row_types]
    rows = response.get("data", [])
    return [dict(zip(col_names, row)) for row in rows]


def get_account_metrics(email: str) -> dict | None:
    """Fetches account health metrics from ACCOUNT_METRICS for the given email."""
    statement = (
        "SELECT EMAIL, ACCOUNT_ID, CURRENT_MONTH_USAGE_GB, QUOTA_GB, "
        "OVERAGE_EVENTS_30D, LAST_QUERY_DATE "
        "FROM ACCOUNT_METRICS WHERE EMAIL = ? LIMIT 1"
    )
    bindings = {"1": {"type": "TEXT", "value": email}}
    response = execute_statement(statement, bindings)
    rows = parse_results(response)
    return rows[0] if rows else None


class AccountHealthCheckController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Meridian Analytics",
            agent_name="Sam",
            agent_purpose=(
                "to help customers understand the health and usage status of their "
                "Meridian Analytics account"
            ),
        )

        self.set_task(
            objective=(
                "A customer has called Meridian Analytics to check the health of their account. "
                "Collect their email address, pull their usage metrics and quota status from "
                "Snowflake, and give them a clear health summary."
            ),
            checklist=[
                guava.Say(
                    "Thank you for calling Meridian Analytics. This is Sam. "
                    "I can give you a complete health summary of your account — "
                    "let me just look that up for you now."
                ),
                guava.Field(
                    key="caller_email",
                    field_type="text",
                    description=(
                        "Ask the caller for the email address linked to their Meridian Analytics account."
                    ),
                    required=True,
                ),
            ],
            on_complete=self.fetch_and_summarize,
        )

        self.accept_call()

    def fetch_and_summarize(self):
        email = self.get_field("caller_email") or ""

        logging.info("Fetching account health metrics for email: %s", email)
        try:
            metrics = get_account_metrics(email.strip().lower())
        except Exception as e:
            logging.error("Snowflake query failed for email %s: %s", email, e)
            self.hangup(
                final_instructions=(
                    "Apologize to the caller and let them know there was a problem retrieving "
                    "their account metrics. Ask them to try again shortly or reach out to "
                    "Meridian Analytics support by email. Thank them for calling."
                )
            )
            return

        if not metrics:
            logging.info("No account metrics found for email: %s", email)
            self.hangup(
                final_instructions=(
                    f"Let the caller know that no account was found for the email '{email}'. "
                    "Ask them to verify their email or contact support if they think this is a mistake. "
                    "Thank them for calling Meridian Analytics."
                )
            )
            return

        account_id = metrics.get("ACCOUNT_ID", "unknown")
        usage_gb = float(metrics.get("CURRENT_MONTH_USAGE_GB") or 0)
        quota_gb = float(metrics.get("QUOTA_GB") or 0)
        overage_events = int(metrics.get("OVERAGE_EVENTS_30D") or 0)
        last_query_date = metrics.get("LAST_QUERY_DATE", "unknown")

        usage_pct = (usage_gb / quota_gb * 100) if quota_gb > 0 else 0

        if usage_pct >= 90:
            health_status = "critical — approaching quota limit"
        elif usage_pct >= 70:
            health_status = "moderate — usage is elevated"
        else:
            health_status = "healthy"

        logging.info(
            "Account %s — usage: %.1f/%.1f GB (%.0f%%), overages: %d, health: %s",
            account_id, usage_gb, quota_gb, usage_pct, overage_events, health_status,
        )

        overage_note = (
            f"there have been {overage_events} overage event{'s' if overage_events != 1 else ''} in the last 30 days"
            if overage_events > 0
            else "there have been no overage events in the last 30 days"
        )

        self.hangup(
            final_instructions=(
                f"Deliver the following account health summary clearly and conversationally: "
                f"account ID {account_id} is currently at {usage_pct:.0f}% of its monthly quota "
                f"({usage_gb:.1f} GB used out of {quota_gb:.1f} GB). The overall health status is {health_status}. "
                f"Additionally, {overage_note}. Their last recorded query activity was on {last_query_date}. "
                "If usage is above 70%, recommend they review their query workloads or consider a quota increase. "
                "Thank them for calling Meridian Analytics."
            )
        )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=AccountHealthCheckController,
    )
