import guava
import os
import logging
from guava import logging_utils
import argparse
import requests
from datetime import datetime, timezone


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


def get_account_alert(account_id: str) -> dict | None:
    """Fetches usage alert data for the given account from ACCOUNT_ALERTS."""
    statement = (
        "SELECT ACCOUNT_ID, CUSTOMER_NAME, CURRENT_USAGE_GB, QUOTA_GB, USAGE_PCT "
        "FROM ACCOUNT_ALERTS WHERE ACCOUNT_ID = ? LIMIT 1"
    )
    bindings = {"1": {"type": "TEXT", "value": account_id}}
    response = execute_statement(statement, bindings)
    rows = parse_results(response)
    return rows[0] if rows else None


def record_alert_response(account_id: str, customer_name: str, decision: str, notes: str) -> None:
    """Inserts the customer's response decision into the ALERT_RESPONSES table."""
    responded_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    statement = (
        "INSERT INTO ALERT_RESPONSES (ACCOUNT_ID, CUSTOMER_NAME, DECISION, NOTES, RESPONDED_AT) "
        "VALUES (?, ?, ?, ?, ?)"
    )
    bindings = {
        "1": {"type": "TEXT", "value": account_id},
        "2": {"type": "TEXT", "value": customer_name},
        "3": {"type": "TEXT", "value": decision},
        "4": {"type": "TEXT", "value": notes},
        "5": {"type": "TEXT", "value": responded_at},
    }
    response = execute_statement(statement, bindings)
    logging.info("Alert response recorded for account %s: %s", account_id, response)


class UsageAlertController(guava.CallController):
    def __init__(self, account_id: str, contact_name: str):
        super().__init__()
        self.account_id = account_id
        self.contact_name = contact_name
        self.current_usage_gb = "unknown"
        self.quota_gb = "unknown"
        self.usage_pct = "unknown"

        # Pre-call: fetch alert data so the agent can reference specific numbers.
        try:
            alert = get_account_alert(account_id)
            if alert:
                self.current_usage_gb = alert.get("CURRENT_USAGE_GB", "unknown")
                self.quota_gb = alert.get("QUOTA_GB", "unknown")
                self.usage_pct = alert.get("USAGE_PCT", "unknown")
                logging.info(
                    "Pre-call alert data for account %s — usage: %s GB / %s GB (%s%%)",
                    account_id, self.current_usage_gb, self.quota_gb, self.usage_pct,
                )
            else:
                logging.warning("No alert record found for account %s", account_id)
        except Exception as e:
            logging.error("Failed to fetch alert data for account %s: %s", account_id, e)

        self.set_persona(
            organization_name="Meridian Analytics",
            agent_name="Taylor",
            agent_purpose=(
                "to notify customers when their Meridian Analytics usage is approaching their "
                "monthly quota and to collect their preferred course of action"
            ),
        )

        self.reach_person(
            contact_full_name=contact_name,
            on_success=self.begin_call,
            on_failure=self.recipient_unavailable,
        )

    def begin_call(self):
        self.set_task(
            objective=(
                f"Notify {self.contact_name} that their Meridian Analytics account "
                f"({self.account_id}) is approaching its monthly quota, and collect "
                "their preferred response: upgrade their plan or reduce usage."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.contact_name}, this is Taylor calling from Meridian Analytics. "
                    f"I'm reaching out because your account is currently at {self.usage_pct}% "
                    f"of its monthly quota — you've used {self.current_usage_gb} GB out of "
                    f"your {self.quota_gb} GB allowance. I wanted to make sure you're aware "
                    "and give you a chance to decide how you'd like to handle this."
                ),
                guava.Field(
                    key="decision",
                    field_type="multiple_choice",
                    description=(
                        "Ask the customer whether they would like to upgrade their plan to get "
                        "more quota, or whether they plan to reduce their usage to stay within "
                        "the current limit. Capture their choice."
                    ),
                    choices=["upgrade_plan", "reduce_usage"],
                    required=True,
                ),
                guava.Field(
                    key="additional_notes",
                    field_type="text",
                    description=(
                        "Ask if they have any questions or additional context about their usage "
                        "that our team should know. Capture their response, or 'none' if they "
                        "have nothing to add."
                    ),
                    required=False,
                ),
            ],
            on_complete=self.save_response,
        )

    def save_response(self):
        decision = self.get_field("decision") or "not_provided"
        notes = self.get_field("additional_notes") or ""

        logging.info(
            "Usage alert response for account %s — decision: %s", self.account_id, decision
        )

        try:
            record_alert_response(
                account_id=self.account_id,
                customer_name=self.contact_name,
                decision=decision,
                notes=notes,
            )
            logging.info("Alert response written to ALERT_RESPONSES for account %s", self.account_id)
        except Exception as e:
            logging.error(
                "Failed to write alert response for account %s: %s", self.account_id, e
            )

        if decision == "upgrade_plan":
            self.hangup(
                final_instructions=(
                    f"Thank {self.contact_name} for their time and let them know that a member of "
                    "the Meridian Analytics team will be in touch shortly to walk them through the "
                    "available plan options and complete the upgrade. Wish them a great day."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Thank {self.contact_name} for their time. Let them know their preference to "
                    "manage usage within the current quota has been noted. Suggest they review "
                    "which queries or workflows are consuming the most data and offer that support "
                    "documentation is available in their account portal. Wish them a great day."
                )
            )

    def recipient_unavailable(self):
        logging.info(
            "Unable to reach %s for usage alert on account %s",
            self.contact_name, self.account_id,
        )
        self.hangup(
            final_instructions=(
                f"Leave a brief voicemail for {self.contact_name} from Meridian Analytics. "
                f"Let them know their account ({self.account_id}) is approaching its monthly "
                "data quota and ask them to log in to their account portal or call us back "
                "to discuss their options. Keep the message concise and professional."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound usage alert call for a Meridian Analytics account approaching quota."
    )
    parser.add_argument("phone", help="Customer phone number to call (E.164 format, e.g. +15551234567)")
    parser.add_argument("--account-id", required=True, help="Meridian Analytics account ID")
    parser.add_argument("--name", required=True, help="Customer's full name")
    args = parser.parse_args()

    logging.info(
        "Initiating usage alert call to %s (%s) for account %s",
        args.name, args.phone, args.account_id,
    )

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=UsageAlertController(
            account_id=args.account_id,
            contact_name=args.name,
        ),
    )
