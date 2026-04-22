import guava
import os
import logging
from guava import logging_utils

from google.oauth2 import service_account
from googleapiclient.discovery import build


SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
SPREADSHEET_ID = os.environ["SHEETS_SPREADSHEET_ID"]
SHEET_NAME = os.environ.get("SHEETS_INVENTORY_TAB", "Inventory")

_sheets_service = None

# Expected sheet columns (0-indexed): SKU | Product Name | Quantity | Location | Unit
COL_SKU = 0
COL_NAME = 1
COL_QTY = 2
COL_LOCATION = 3
COL_UNIT = 4


def build_sheets_service():
    creds = service_account.Credentials.from_service_account_file(
        os.environ["GOOGLE_CREDENTIALS_FILE"],
        scopes=SCOPES,
    )
    return build("sheets", "v4", credentials=creds)


def lookup_product(service, query: str) -> dict | None:
    """Finds the first row whose SKU or product name matches query (case-insensitive).

    Returns a dict with sku, name, quantity, location, unit, or None if not found.
    """
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=SPREADSHEET_ID, range=f"{SHEET_NAME}!A:E")
        .execute()
    )
    rows = result.get("values", [])

    query_lower = query.lower().strip()
    for row in rows[1:]:  # skip header row
        if len(row) < 3:
            continue
        sku = row[COL_SKU] if len(row) > COL_SKU else ""
        name = row[COL_NAME] if len(row) > COL_NAME else ""
        if query_lower in sku.lower() or query_lower in name.lower():
            return {
                "sku": sku,
                "name": name,
                "quantity": row[COL_QTY] if len(row) > COL_QTY else "unknown",
                "location": row[COL_LOCATION] if len(row) > COL_LOCATION else "",
                "unit": row[COL_UNIT] if len(row) > COL_UNIT else "units",
            }
    return None


agent = guava.Agent(
    name="Sam",
    organization="Apex Solutions",
    purpose=(
        "to help staff and partners quickly check current inventory levels "
        "from the Apex Solutions product catalog"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    global _sheets_service
    _sheets_service = build_sheets_service()

    call.set_task(
        "report_inventory",
        objective=(
            "A caller wants to check how many units of a product are currently in stock. "
            "Ask for the product name or SKU and read back the inventory details."
        ),
        checklist=[
            guava.Say(
                "Thanks for calling Apex Solutions inventory. I'm Sam. "
                "I can look up current stock levels — what product are you checking on?"
            ),
            guava.Field(
                key="product_query",
                field_type="text",
                description=(
                    "Ask for the product name or SKU they want to check. "
                    "A partial name is fine."
                ),
                required=True,
            ),
        ],
    )


@agent.on_task_complete("report_inventory")
def on_done(call: guava.Call) -> None:
    query = (call.get_field("product_query") or "").strip()
    logging.info("Inventory lookup — query: '%s'", query)

    try:
        product = lookup_product(_sheets_service, query)
    except Exception as e:
        logging.error("Sheets lookup failed: %s", e)
        call.hangup(
            final_instructions=(
                "Apologize — there was a technical issue accessing the inventory sheet. "
                "Ask the caller to check the sheet directly or try again in a moment."
            )
        )
        return

    if not product:
        call.hangup(
            final_instructions=(
                f"Let the caller know we couldn't find a product matching '{query}' "
                "in the inventory sheet. Ask them to double-check the name or SKU "
                "and try again. Thank them for calling."
            )
        )
        return

    qty = product["quantity"]
    name = product["name"]
    sku = product["sku"]
    location = product["location"]
    unit = product["unit"]

    location_phrase = f", located in {location}" if location else ""
    logging.info("Found product '%s' (SKU %s): %s %s%s", name, sku, qty, unit, location_phrase)

    call.hangup(
        final_instructions=(
            f"Let the caller know that {name} (SKU: {sku}) currently has "
            f"{qty} {unit} in stock{location_phrase}. "
            "Thank them for calling Apex Solutions."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
