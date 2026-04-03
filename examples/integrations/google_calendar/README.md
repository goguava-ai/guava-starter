# Google Calendar Integration

An inbound voice agent that answers calls and books consultation appointments directly into a Google Calendar. The agent queries real availability via the Calendar freebusy API, presents open slots conversationally, and creates the event once the caller confirms a time — all within a single phone call.

## How It Works

**1. Fetch availability at call start**

When a call comes in, `get_free_slots()` queries the Google Calendar freebusy API for the next 14 days and builds a list of open ISO-8601 datetime strings. These are loaded into a `DatetimeFilter` once per call.

**2. Collect the caller's name**

A `text` field gathers the caller's full name to attach to the calendar event.

**3. Find a slot using natural language**

A `calendar_slot` field handles slot selection. When the caller expresses a preference ("Tuesday morning", "sometime next week after 2"), guava calls `filter_slots()`, which passes the phrase to `DatetimeFilter`. The filter uses Gemini to match the caller's intent against the real available slot list and returns up to 3 matching times (and fallbacks if nothing matches exactly). Guava presents these to the caller and collects their confirmation.

**4. Book the event**

Once the caller picks a time, `finalize_booking()` calls `book_slot()`, which posts a new event to Google Calendar via `events().insert()`.

## Google Calendar API Calls

| Timing | Method | Purpose |
|---|---|---|
| Call start | `freebusy().query()` | Get all busy periods in the booking window |
| Post-confirm | `events().insert()` | Create the booked appointment |

## Setup

### 1. Create a Google Cloud service account

1. Go to [console.cloud.google.com](https://console.cloud.google.com) → **IAM & Admin** → **Service Accounts**.
2. Create a service account and download its JSON key file.
3. Enable the **Google Calendar API** for your project.

### 2. Share your calendar with the service account

In Google Calendar, open the calendar's settings → **Share with specific people** → add the service account email with **"Make changes to events"** permission.

### 3. Install dependencies

```bash
pip install guava google-api-python-client google-auth google-genai
```

### 4. Set environment variables

```bash
export GUAVA_AGENT_NUMBER="+1..."
export GOOGLE_CREDENTIALS_FILE="/path/to/service-account.json"
export GOOGLE_CALENDAR_ID="your-calendar-id@group.calendar.google.com"
```

Use `"primary"` as `GOOGLE_CALENDAR_ID` to book into the service account's own calendar.

### 5. Run

```bash
python -m examples.integrations.google_calendar
```

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `GOOGLE_CREDENTIALS_FILE` | Path to the service account JSON key file |
| `GOOGLE_CALENDAR_ID` | Calendar ID to book into (e.g. `primary` or a full address) |
| `APPOINTMENT_DURATION_MINS` | Slot length in minutes (default: `30`) |
| `BOOKING_WINDOW_DAYS` | How many days ahead to search (default: `14`) |
| `BUSINESS_HOURS_START` | Start of bookable hours, 24h (default: `9`) |
| `BUSINESS_HOURS_END` | End of bookable hours, 24h (default: `17`) |
