import guava
import os
import logging
from guava import logging_utils
import requests
from urllib.parse import quote


BASE_ID = os.environ["AIRTABLE_BASE_ID"]
TABLE_NAME = os.environ.get("AIRTABLE_TABLE_NAME", "Records")
BASE_URL = f"https://api.airtable.com/v0/{BASE_ID}/{quote(TABLE_NAME)}"


def get_headers() -> dict:
    return {
        "Authorization": f"Bearer {os.environ['AIRTABLE_API_KEY']}",
        "Content-Type": "application/json",
    }


def search_records(query: str, field: str = "Name") -> list[dict]:
    """Search Airtable records using a filterByFormula."""
    formula = f"SEARCH(LOWER('{query}'), LOWER({{{field}}}))"
    params = {"filterByFormula": formula, "maxRecords": 5}
    resp = requests.get(BASE_URL, headers=get_headers(), params=params, timeout=10)
    resp.raise_for_status()
    return resp.json().get("records", [])


class RecordLookupController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Meridian Team",
            agent_name="Alex",
            agent_purpose="to help Meridian Team members look up records in Airtable over the phone",
        )

        self.set_task(
            objective=(
                "A team member has called to look up a record in Airtable. "
                "Collect their search query, find the record, and read back the details."
            ),
            checklist=[
                guava.Say(
                    "Meridian Team records lookup, this is Alex. What record are you looking for today?"
                ),
                guava.Field(
                    key="search_query",
                    field_type="text",
                    description="Ask for the name or identifier of the record they want to look up.",
                    required=True,
                ),
                guava.Field(
                    key="search_field",
                    field_type="multiple_choice",
                    description="Ask which field to search by.",
                    choices=["Name", "Email", "ID", "Company"],
                    required=False,
                ),
            ],
            on_complete=self.lookup_record,
        )

        self.accept_call()

    def lookup_record(self):
        search_query = self.get_field("search_query") or ""
        search_field = self.get_field("search_field") or "Name"

        logging.info("Looking up Airtable record: query=%s, field=%s", search_query, search_field)

        records = []
        try:
            records = search_records(search_query, field=search_field)
            logging.info("Found %d records matching '%s'", len(records), search_query)
        except Exception as e:
            logging.error("Failed to search Airtable: %s", e)

        if not records:
            self.hangup(
                final_instructions=(
                    f"Let the caller know no records were found matching '{search_query}' in the {search_field} field. "
                    "They may want to try a different search term. Thank them and end the call."
                )
            )
            return

        record = records[0]
        fields = record.get("fields", {})
        record_id = record.get("id", "")

        field_summary = ", ".join(f"{k}: {v}" for k, v in list(fields.items())[:6] if v)

        if len(records) > 1:
            additional = f"There are {len(records) - 1} additional matching records."
        else:
            additional = ""

        self.hangup(
            final_instructions=(
                f"Read back the following record details to the caller: {field_summary}. "
                f"(Record ID: {record_id}.) "
                + (f"{additional} " if additional else "")
                + "Thank them for calling."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=RecordLookupController,
    )
