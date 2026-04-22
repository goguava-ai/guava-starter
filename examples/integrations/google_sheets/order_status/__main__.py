import guava
import os
import logging
from guava import logging_utils

from google.oauth2 import service_account
from googleapiclient.discovery import build


SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
SPREADSHEET_ID = os.environ["SHEETS_SPREADSHEET_ID"]
SHEET_NAME = os.environ.get("SHEETS_ORDERS_TAB", "Orders")

# Expected sheet columns (0-indexed):
# Order ID | Last Name | Status | Est. Delivery | Items Summary | Tracking Number
COL_ORDER_ID = 0
COL_LAST_NAME = 1
COL_STATUS = 2
COL_DELIVERY = 3
COL_ITEMS = 4
COL_TRACKING = 5


def build_sheets_service():
    creds = service_account.Credentials.from_service_account_file(
        os.environ["GOOGLE_CREDENTIALS_FILE"],
        scopes=SCOPES,
    )
    return build("sheets", "v4", credentials=creds)


def find_order(service, order_id: str, last_name: str) -> dict | None:
    """Finds an order by ID and verifies it with the customer's last name.

    Returns an order dict or None if not found / name doesn't match.
    """
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=SPREADSHEET_ID, range=f"{SHEET_NAME}!A:F")
        .execute()
    )
    rows = result.get("values", [])

    order_id_clean = order_id.strip().upper()
    last_name_clean = last_name.strip().lower()

    for row in rows[1:]:  # skip header
        if not row:
            continue
        row_order_id = (row[COL_ORDER_ID] if len(row) > COL_ORDER_ID else "").strip().upper()
        row_last_name = (row[COL_LAST_NAME] if len(row) > COL_LAST_NAME else "").strip().lower()

        if row_order_id == order_id_clean and row_last_name == last_name_clean:
            return {
                "order_id": row[COL_ORDER_ID],
                "status": row[COL_STATUS] if len(row) > COL_STATUS else "unknown",
                "delivery": row[COL_DELIVERY] if len(row) > COL_DELIVERY else "",
                "items": row[COL_ITEMS] if len(row) > COL_ITEMS else "",
                "tracking": row[COL_TRACKING] if len(row) > COL_TRACKING else "",
            }
    return None


class OrderStatusController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.service = build_sheets_service()

        self.set_persona(
            organization_name="Apex Solutions",
            agent_name="Riley",
            agent_purpose=(
                "to help customers quickly check the status of their orders "
                "without needing to navigate the website"
            ),
        )

        self.set_task(
            objective=(
                "A customer has called to check on an order. "
                "Verify their identity with their order number and last name, "
                "then read back the order status and delivery estimate."
            ),
            checklist=[
                guava.Say(
                    "Thanks for calling Apex Solutions support. I'm Riley. "
                    "I can pull up your order right now — I just need to verify a couple of things."
                ),
                guava.Field(
                    key="order_id",
                    field_type="text",
                    description=(
                        "Ask for their order number. Let them know it's on their "
                        "confirmation email and starts with a letter or number."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="last_name",
                    field_type="text",
                    description="Ask for the last name on the order for verification.",
                    required=True,
                ),
            ],
            on_complete=self.deliver_status,
        )

        self.accept_call()

    def deliver_status(self):
        order_id = (self.get_field("order_id") or "").strip()
        last_name = (self.get_field("last_name") or "").strip()

        logging.info("Order lookup — order_id: '%s', last_name: '%s'", order_id, last_name)

        try:
            order = find_order(self.service, order_id, last_name)
        except Exception as e:
            logging.error("Sheets lookup failed: %s", e)
            self.hangup(
                final_instructions=(
                    "Apologize — there was a technical issue looking up the order. "
                    "Ask the caller to visit the website or try again shortly. Thank them."
                )
            )
            return

        if not order:
            self.hangup(
                final_instructions=(
                    f"Let the caller know we couldn't find order '{order_id}' under that last name. "
                    "Ask them to double-check the order number and last name from their "
                    "confirmation email. Offer to transfer to a support agent if needed. "
                    "Be polite and empathetic."
                )
            )
            return

        status = order["status"]
        delivery = order["delivery"]
        items = order["items"]
        tracking = order["tracking"]

        delivery_phrase = f" with an estimated delivery of {delivery}" if delivery else ""
        items_phrase = f" containing {items}" if items else ""
        tracking_phrase = f" Their tracking number is {tracking}." if tracking else ""

        logging.info("Order %s status: %s, delivery: %s", order_id, status, delivery)

        self.hangup(
            final_instructions=(
                f"Let the caller know order {order_id}{items_phrase} is currently '{status}'"
                f"{delivery_phrase}.{tracking_phrase} "
                "If the status is 'shipped', remind them they can use the tracking number "
                "on the carrier's website for real-time updates. "
                "Thank them for calling Apex Solutions."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=OrderStatusController,
    )
