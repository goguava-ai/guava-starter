# Availability Check

**Direction:** Inbound

A client calls Crestwood Wellness to check what appointment slots are open. The agent collects their service preference and desired week, searches Square for real available slots, presents up to five options conversationally, and offers to book on the spot.

## What it does

1. Collects service type, preferred week, and preferred time of day
2. Searches for open slots via `POST /v2/bookings/availability/search` using the `SQUARE_SERVICE_VARIATION_ID` and `SQUARE_TEAM_MEMBER_ID`
3. Filters results by time-of-day preference (morning / afternoon / evening / flexible)
4. Reads back the first 3–5 available slots in a natural, conversational way
5. Asks if the caller wants to book immediately; if yes:
   - Looks up the customer via `POST /v2/customers/search` (email)
   - Creates the customer via `POST /v2/customers` if not found
   - Books the chosen slot via `POST /v2/bookings`
   - Reads back the confirmation ID

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `SQUARE_ACCESS_TOKEN` | Square access token from the Developer Dashboard |
| `SQUARE_LOCATION_ID` | Your Square location ID |
| `SQUARE_SERVICE_VARIATION_ID` | The catalog item variation ID for the service to search |
| `SQUARE_TEAM_MEMBER_ID` | The team member ID to filter availability for |

## Usage

```bash
python -m examples.integrations.square_appointments.availability_check
```

## Finding your Service Variation ID

Use the Square Catalog API to list your services:

```bash
curl -H "Authorization: Bearer $SQUARE_ACCESS_TOKEN" \
     -H "Square-Version: 2024-01-17" \
     "https://connect.squareup.com/v2/catalog/list?types=ITEM,ITEM_VARIATION"
```

Look for the `id` field on the `ITEM_VARIATION` objects that correspond to your bookable services.
