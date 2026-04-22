import logging
import os

import guava
import requests
from guava import logging_utils

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
    payload: dict[str, object] = {
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


def lookup_customer(email: str) -> dict | None:
    """Looks up a customer record in the CUSTOMERS table by email address."""
    statement = (
        "SELECT EMAIL, CUSTOMER_NAME, PLAN, MONTHLY_USAGE_GB, JOIN_DATE, ACCOUNT_STATUS "
        "FROM CUSTOMERS WHERE EMAIL = ? LIMIT 1"
    )
    bindings = {"1": {"type": "TEXT", "value": email}}
    response = execute_statement(statement, bindings)
    rows = parse_results(response)
    return rows[0] if rows else None


agent = guava.Agent(
    name="Alex",
    organization="Meridian Analytics",
    purpose=(
        "to help customers look up their account information stored with Meridian Analytics"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "fetch_and_deliver",
        objective=(
            "A customer has called Meridian Analytics to review their account details. "
            "Collect their email address, look up their account, and read back their "
            "current plan, usage, and account status."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Meridian Analytics. My name is Alex. "
                "I can pull up your account details right now — "
                "I just need to verify a couple of things first."
            ),
            guava.Field(
                key="caller_email",
                field_type="text",
                description=(
                    "Ask the caller for the email address associated with their Meridian Analytics account."
                ),
                required=True,
            ),
        ],
    )


@agent.on_task_complete("fetch_and_deliver")
def fetch_and_deliver(call: guava.Call) -> None:
    email = call.get_field("caller_email") or ""

    logging.info("Looking up customer account for email: %s", email)
    try:
        customer = lookup_customer(email.strip().lower())
    except Exception as e:
        logging.error("Snowflake query failed for email %s: %s", email, e)
        call.hangup(
            final_instructions=(
                "Apologize to the caller and let them know there was a technical issue "
                "retrieving their account. Ask them to try again in a few minutes or "
                "contact support by email. Thank them for their patience."
            )
        )
        return

    if not customer:
        logging.info("No customer found for email: %s", email)
        call.hangup(
            final_instructions=(
                f"Let the caller know that no account was found for the email address "
                f"'{email}'. Ask them to double-check the address or contact support "
                "if they believe this is an error. Thank them for calling Meridian Analytics."
            )
        )
        return

    name = customer.get("CUSTOMER_NAME", "there")
    plan = customer.get("PLAN", "unknown")
    usage_gb = customer.get("MONTHLY_USAGE_GB", "unknown")
    join_date = customer.get("JOIN_DATE", "unknown")
    status = customer.get("ACCOUNT_STATUS", "unknown")

    logging.info(
        "Account found for %s — plan: %s, usage: %s GB, status: %s",
        name, plan, usage_gb, status,
    )

    call.hangup(
        final_instructions=(
            f"Greet {name} by name and read back the following account details clearly: "
            f"their current plan is '{plan}', they have used {usage_gb} GB this month, "
            f"they joined on {join_date}, and their account status is '{status}'. "
            "Thank them for calling Meridian Analytics and wish them a great day."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
