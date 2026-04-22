import logging
import os
from urllib.parse import quote

import guava
import requests
from guava import logging_utils

BASE_ID = os.environ["AIRTABLE_BASE_ID"]
TABLE_NAME = os.environ.get("AIRTABLE_TABLE_NAME", "Records")
BASE_URL = f"https://api.airtable.com/v0/{BASE_ID}/{quote(TABLE_NAME)}"


def get_headers() -> dict:
    return {
        "Authorization": f"Bearer {os.environ['AIRTABLE_API_KEY']}",
        "Content-Type": "application/json",
    }


def find_record(query: str, field: str = "Name") -> dict | None:
    formula = f"SEARCH(LOWER('{query}'), LOWER({{{field}}}))"
    params = {"filterByFormula": formula, "maxRecords": 1}
    resp = requests.get(BASE_URL, headers=get_headers(), params=params, timeout=10)
    resp.raise_for_status()
    records = resp.json().get("records", [])
    return records[0] if records else None


def update_record(record_id: str, fields: dict) -> dict | None:
    resp = requests.patch(
        f"{BASE_URL}/{record_id}",
        headers=get_headers(),
        json={"fields": fields},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


agent = guava.Agent(
    name="Alex",
    organization="Meridian Team",
    purpose="to help Meridian Team members update records in Airtable over the phone",
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "update_record",
        objective=(
            "A team member has called to update a record in Airtable. "
            "Find the record by name or identifier, confirm the field to update, "
            "collect the new value, and apply the update."
        ),
        checklist=[
            guava.Say(
                "Meridian Team records, this is Alex. I can help you update a record today."
            ),
            guava.Field(
                key="record_name",
                field_type="text",
                description="Ask for the name or identifier of the record to update.",
                required=True,
            ),
            guava.Field(
                key="field_to_update",
                field_type="multiple_choice",
                description="Ask which field they'd like to update.",
                choices=["Status", "Notes", "Priority", "Assignee", "Due Date", "Other"],
                required=True,
            ),
            guava.Field(
                key="custom_field_name",
                field_type="text",
                description="If they selected 'Other', ask for the exact field name.",
                required=False,
            ),
            guava.Field(
                key="new_value",
                field_type="text",
                description="Ask for the new value for that field.",
                required=True,
            ),
        ],
    )


@agent.on_task_complete("update_record")
def on_done(call: guava.Call) -> None:
    record_name = call.get_field("record_name") or ""
    field_to_update = call.get_field("field_to_update") or ""
    custom_field_name = call.get_field("custom_field_name") or ""
    new_value = call.get_field("new_value") or ""

    field_name = custom_field_name if field_to_update == "Other" and custom_field_name else field_to_update

    logging.info("Updating Airtable record '%s': %s = %s", record_name, field_name, new_value)

    record = None
    try:
        record = find_record(record_name)
    except Exception as e:
        logging.error("Failed to find record '%s': %s", record_name, e)

    if not record:
        call.hangup(
            final_instructions=(
                f"Let the caller know no record named '{record_name}' was found. "
                "They may want to double-check the name and try again. "
                "Thank them for calling."
            )
        )
        return

    record_id = record["id"]
    updated = None
    try:
        updated = update_record(record_id, {field_name: new_value})
        logging.info("Updated record %s: %s = %s", record_id, field_name, new_value)
    except Exception as e:
        logging.error("Failed to update record %s: %s", record_id, e)

    if updated:
        call.hangup(
            final_instructions=(
                f"Let the caller know the record '{record_name}' has been updated: "
                f"{field_name} is now set to '{new_value}'. "
                "Thank them for calling."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Apologize — we were unable to update the record '{record_name}' automatically. "
                "Ask them to make the change directly in Airtable or contact the Meridian Team admin. "
                "Thank them for their patience."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
