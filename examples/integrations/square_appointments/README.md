# Square Appointments Integration

Voice agents that integrate with the [Square Bookings API](https://developer.squareup.com/reference/square/bookings-api) to handle appointment booking, cancellation, rescheduling, reminders, and availability checks — for wellness studios, salons, fitness facilities, and other appointment-based businesses running on Square.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`appointment_booking`](appointment_booking/) | Inbound | Client calls to book an appointment; agent collects details, finds or creates their customer record, and confirms a booking |
| [`appointment_cancellation`](appointment_cancellation/) | Inbound | Client calls to cancel or reschedule; agent verifies the booking and processes the request |
| [`appointment_reminder`](appointment_reminder/) | Outbound | Proactively calls clients before upcoming appointments to confirm attendance and handle same-call cancellations |
| [`availability_check`](availability_check/) | Inbound | Client calls to check open slots; agent searches real availability and offers to book on the spot |

## Authentication

All examples authenticate with a Square access token passed as a Bearer token:

```python
HEADERS = {
    "Authorization": f"Bearer {SQUARE_ACCESS_TOKEN}",
    "Content-Type": "application/json",
    "Square-Version": "2024-01-17",
}
```

Get your access token from the [Square Developer Dashboard](https://developer.squareup.com/apps). Use a **sandbox** token for testing and a **production** token for live calls.

> **Note on the Square-Version header:** All requests must include `Square-Version: 2024-01-17`. This pins the API contract and ensures responses remain consistent. Square may introduce breaking changes in newer versions — update this header deliberately after reviewing the [Square changelog](https://developer.squareup.com/docs/changelog/connect).

## Common Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `SQUARE_ACCESS_TOKEN` | Square access token (sandbox or production) |
| `SQUARE_LOCATION_ID` | Your Square location ID (find it in the Developer Dashboard or via `GET /v2/locations`) |
| `SQUARE_SERVICE_VARIATION_ID` | The catalog item variation ID for the bookable service (see below) |
| `SQUARE_TEAM_MEMBER_ID` | The team member ID to assign appointments to (see `GET /v2/team-members`) |

## Usage

Inbound examples (start a listener for incoming calls):

```bash
python -m examples.integrations.square_appointments.appointment_booking
python -m examples.integrations.square_appointments.appointment_cancellation
python -m examples.integrations.square_appointments.availability_check
```

Outbound example (initiate a single reminder call):

```bash
python -m examples.integrations.square_appointments.appointment_reminder \
  "+15551234567" \
  --booking-id "booking_abc123" \
  --name "Alex Rivera"
```

## Finding Your Service Variation ID

Retrieve bookable services from your Square catalog:

```bash
curl -H "Authorization: Bearer $SQUARE_ACCESS_TOKEN" \
     -H "Square-Version: 2024-01-17" \
     "https://connect.squareup.com/v2/catalog/list?types=ITEM,ITEM_VARIATION"
```

Look for the `id` field on `ITEM_VARIATION` objects. Set `SQUARE_SERVICE_VARIATION_ID` to the variation ID that corresponds to the service you want to book.

## Square API Reference

- [Bookings API](https://developer.squareup.com/reference/square/bookings-api)
- [Customers API](https://developer.squareup.com/reference/square/customers-api)
- [Catalog API](https://developer.squareup.com/reference/square/catalog-api)
- [Team Members API](https://developer.squareup.com/reference/square/team-api)
- [Locations API](https://developer.squareup.com/reference/square/locations-api)
