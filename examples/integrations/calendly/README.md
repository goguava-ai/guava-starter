# Calendly Integration

An inbound voice agent that answers calls and books meetings directly into Calendly using the [Calendly Scheduling API](https://developer.calendly.com/api-docs/p3ghrxrwbl8kqe-create-event-invitee). The agent fetches your live event types, lets the caller choose the right meeting type, finds a time in natural language, and creates a confirmed invitee — triggering Calendly's standard calendar invites, confirmation emails, and workflows automatically.

## How It Works

**1. Map intent to event type**

At call start, `GET /event_types` fetches all active event types for your account. The agent presents them as choices and maps the caller's intent to the right one (e.g. "30-Minute Demo" vs "Onboarding Call").

**2. Select a timeslot**

`GET /event_type_available_times` is called for the chosen event type, paged in 7-day chunks to cover the full booking window. A `DatetimeFilter` lets the caller express a preference in natural language ("Thursday afternoon", "sometime next week") and matches it against the real available slot list.

**3. Create the invitee**

`POST /invitees` books the meeting with the chosen time and caller details. Calendly handles everything from there — calendar invites, confirmation emails, reminders, and any configured workflows.

**4. Confirm with management links**

The returned `cancel_url` and `reschedule_url` are logged after booking.

## Free Tier Fallback

The Scheduling API (`POST /invitees`) requires a paid Calendly plan. If the account is on the free tier, the agent catches the `403` response and falls back to `POST /scheduling_links`, creating a single-use booking URL. The agent reads the link to the caller so they can complete the booking themselves.

## Calendly API Calls

| Timing | Endpoint | Purpose |
|---|---|---|
| Call start | `GET /users/me` | Get the current user URI |
| Call start | `GET /event_types` | Fetch active event types |
| After meeting type chosen | `GET /event_type_available_times` | Fetch open slots (paged in 7-day chunks) |
| Post-confirm | `POST /invitees` | Create the booking and trigger notifications |
| Post-confirm (fallback) | `POST /scheduling_links` | Single-use booking link for free-tier accounts |

## Setup

### 1. Get a Calendly Personal Access Token

Go to [calendly.com/integrations/api_webhooks](https://calendly.com/integrations/api_webhooks) → **Generate New Token**.

### 2. Install dependencies

```bash
pip install guava requests google-genai
```

### 3. Set environment variables

```bash
export GUAVA_AGENT_NUMBER="+1..."
export CALENDLY_TOKEN="<your_personal_access_token>"
```

### 4. Run

```bash
python -m examples.integrations.calendly
```

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `CALENDLY_TOKEN` | Calendly personal access token |
| `BOOKING_WINDOW_DAYS` | How many days ahead to search (default: `14`) |
