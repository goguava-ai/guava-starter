import guava
import os
import logging
from guava import logging_utils
import argparse
import requests
from datetime import datetime


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


def get_query_result(query_id: str) -> dict | None:
    """Fetches a completed scheduled query result from SCHEDULED_QUERY_RESULTS."""
    statement = (
        "SELECT QUERY_ID, ANALYST_NAME, QUERY_NAME, ROW_COUNT, STATUS, "
        "COMPLETION_TIME, SUMMARY_TEXT "
        "FROM SCHEDULED_QUERY_RESULTS WHERE QUERY_ID = ? LIMIT 1"
    )
    bindings = {"1": {"type": "TEXT", "value": query_id}}
    response = execute_statement(statement, bindings)
    rows = parse_results(response)
    return rows[0] if rows else None


class QueryResultDeliveryController(guava.CallController):
    def __init__(self, query_id: str, contact_name: str):
        super().__init__()
        self.query_id = query_id
        self.contact_name = contact_name
        self.query_name = "your scheduled query"
        self.row_count = "an unknown number of"
        self.status = "completed"
        self.completion_time = "recently"
        self.summary_text = ""

        # Pre-call: fetch the query result record so the agent has the full summary ready.
        try:
            result = get_query_result(query_id)
            if result:
                self.query_name = result.get("QUERY_NAME") or self.query_name
                row_count_raw = result.get("ROW_COUNT")
                self.row_count = str(row_count_raw) if row_count_raw is not None else self.row_count
                self.status = result.get("STATUS") or self.status
                self.completion_time = result.get("COMPLETION_TIME") or self.completion_time
                self.summary_text = result.get("SUMMARY_TEXT") or ""
                logging.info(
                    "Pre-call result for query %s — name: %s, rows: %s, status: %s",
                    query_id, self.query_name, self.row_count, self.status,
                )
            else:
                logging.warning("No result record found for query ID %s", query_id)
        except Exception as e:
            logging.error("Failed to fetch query result for query %s: %s", query_id, e)

        self.set_persona(
            organization_name="Meridian Analytics",
            agent_name="Morgan",
            agent_purpose=(
                "to deliver the results of completed long-running Snowflake queries to "
                "data analysts on behalf of Meridian Analytics"
            ),
        )

        self.reach_person(
            contact_full_name=contact_name,
            on_success=self.deliver_results,
            on_failure=self.recipient_unavailable,
        )

    def deliver_results(self):
        has_summary = bool(self.summary_text and self.summary_text.strip())

        self.set_task(
            objective=(
                f"Deliver the results of the completed Snowflake query '{self.query_name}' "
                f"to {self.contact_name} and confirm they have what they need."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.contact_name}, this is Morgan calling from Meridian Analytics. "
                    f"I'm calling to let you know that your scheduled query '{self.query_name}' "
                    f"has finished running. It completed at {self.completion_time} with a status "
                    f"of '{self.status}' and returned {self.row_count} rows."
                    + (
                        f" Here's a summary of the results: {self.summary_text}"
                        if has_summary
                        else " The full results are available in your Meridian Analytics dashboard."
                    )
                ),
                guava.Field(
                    key="acknowledged",
                    field_type="multiple_choice",
                    description=(
                        "Confirm the analyst received the information. Ask if they were "
                        "able to hear the results clearly and if they have what they need."
                    ),
                    choices=["yes", "no"],
                    required=True,
                ),
                guava.Field(
                    key="follow_up_needed",
                    field_type="multiple_choice",
                    description=(
                        "Ask if they would like a follow-up from the data engineering team "
                        "to walk through the results or if they have any concerns about the output."
                    ),
                    choices=["yes", "no"],
                    required=True,
                ),
                guava.Field(
                    key="follow_up_detail",
                    field_type="text",
                    description=(
                        "If they want a follow-up, ask them to briefly describe what they need "
                        "help with. Capture their response. Skip if they said no."
                    ),
                    required=False,
                ),
            ],
            on_complete=self.wrap_up,
        )

    def wrap_up(self):
        follow_up_needed = self.get_field("follow_up_needed") or "no"
        follow_up_detail = self.get_field("follow_up_detail") or ""

        logging.info(
            "Query result delivery complete for query %s — follow-up needed: %s",
            self.query_id, follow_up_needed,
        )

        if follow_up_needed == "yes":
            self.hangup(
                final_instructions=(
                    f"Let {self.contact_name} know that their follow-up request has been noted "
                    "and the data engineering team will be in touch shortly. "
                    + (
                        f"Their specific request was: {follow_up_detail}. "
                        if follow_up_detail
                        else ""
                    )
                    + "Thank them for their time and wish them a productive day."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Thank {self.contact_name} for their time. Let them know the full result set "
                    "is available in their Meridian Analytics dashboard and they can re-run or "
                    "schedule the query anytime from there. Wish them a great day."
                )
            )

    def recipient_unavailable(self):
        logging.info(
            "Unable to reach %s for query result delivery of query %s",
            self.contact_name, self.query_id,
        )
        self.hangup(
            final_instructions=(
                f"Leave a brief voicemail for {self.contact_name} from Meridian Analytics. "
                f"Let them know their scheduled query '{self.query_name}' has completed "
                f"and the results are ready in their dashboard. "
                "Keep the message short and professional."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound call to deliver completed Snowflake query results to a data analyst."
    )
    parser.add_argument("phone", help="Analyst phone number to call (E.164 format, e.g. +15551234567)")
    parser.add_argument("--query-id", required=True, help="Scheduled query ID from SCHEDULED_QUERY_RESULTS")
    parser.add_argument("--name", required=True, help="Analyst's full name")
    args = parser.parse_args()

    logging.info(
        "Initiating query result delivery call to %s (%s) for query %s",
        args.name, args.phone, args.query_id,
    )

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=QueryResultDeliveryController(
            query_id=args.query_id,
            contact_name=args.name,
        ),
    )
