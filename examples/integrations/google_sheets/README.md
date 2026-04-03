# Google Sheets Integration

Voice agents that read from and write to Google Sheets via the [Sheets API v4](https://developers.google.com/sheets/api/reference/rest). Useful for teams that use Sheets as a lightweight database for leads, orders, inventory, or survey data.

## Examples

| Example | Direction | Description | Sheets Operation |
|---|---|---|---|
| [`lead_capture`](lead_capture/) | Inbound | Caller expresses interest; agent collects name, email, phone, and interest area and appends a row to a Leads sheet | `values.append` |
| [`inventory_lookup`](inventory_lookup/) | Inbound | Caller checks current stock levels for a product by name or SKU | `values.get` |
| [`order_status`](order_status/) | Inbound | Customer calls with an order number; agent verifies identity and reads back status and delivery estimate | `values.get` |
| [`survey_collector`](survey_collector/) | Outbound | Post-service satisfaction call; collects rating, highlight, and improvement suggestion, then appends to a responses sheet | `values.append` |

## Authentication

All examples authenticate using a Google service account. Download a JSON key file from the [Google Cloud Console](https://console.cloud.google.com/iam-admin/serviceaccounts) and share your spreadsheet with the service account's email address.

```python
from google.oauth2 import service_account
from googleapiclient.discovery import build

creds = service_account.Credentials.from_service_account_file(
    os.environ["GOOGLE_CREDENTIALS_FILE"],
    scopes=["https://www.googleapis.com/auth/spreadsheets"],
)
service = build("sheets", "v4", credentials=creds)
```

Read-only examples use the narrower `spreadsheets.readonly` scope.

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `GOOGLE_CREDENTIALS_FILE` | Path to your service account JSON key file |
| `SHEETS_SPREADSHEET_ID` | The spreadsheet ID from its URL |
| `SHEETS_LEAD_TAB` | Sheet tab name for leads (default: `Leads`) |
| `SHEETS_INVENTORY_TAB` | Sheet tab name for inventory (default: `Inventory`) |
| `SHEETS_ORDERS_TAB` | Sheet tab name for orders (default: `Orders`) |
| `SHEETS_SURVEY_TAB` | Sheet tab name for survey responses (default: `Survey Responses`) |

## Sheet Layouts

Each example expects a specific column layout (row 1 is a header and is skipped on reads):

**Leads** — `Timestamp | Name | Email | Phone | Interest | Status`

**Inventory** — `SKU | Product Name | Quantity | Location | Unit`

**Orders** — `Order ID | Last Name | Status | Est. Delivery | Items Summary | Tracking Number`

**Survey Responses** — `Timestamp | Name | Phone | Rating | What Went Well | Improvement | Would Recommend`

## Common Patterns

**Reading rows** — Fetch the full range (`A:F`), skip the header, search rows for a matching value:

```python
result = service.spreadsheets().values().get(
    spreadsheetId=SPREADSHEET_ID, range="Sheet1!A:F"
).execute()
rows = result.get("values", [])
```

**Appending a row** — Use `valueInputOption="USER_ENTERED"` so Sheets parses dates and numbers:

```python
service.spreadsheets().values().append(
    spreadsheetId=SPREADSHEET_ID,
    range="Sheet1!A1",
    valueInputOption="USER_ENTERED",
    body={"values": [[col1, col2, col3]]},
).execute()
```

## Usage

Inbound examples:

```bash
python -m examples.integrations.google_sheets.lead_capture
python -m examples.integrations.google_sheets.inventory_lookup
python -m examples.integrations.google_sheets.order_status
```

Outbound example:

```bash
python -m examples.integrations.google_sheets.survey_collector \
  "+15551234567" --name "Jane Smith"
```
