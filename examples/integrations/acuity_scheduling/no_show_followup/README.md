# No-Show Followup

**Direction:** Outbound

Calls clients who missed their appointment to check in and offer to rebook. Pre-loads the next available slot before the call so the agent can offer a specific time immediately.

## What it does

1. Fetches the missed appointment via `GET /appointments/{id}`
2. Pre-loads the next available slot via `GET /availability/times`
3. Calls the client, asks why they missed the appointment, and offers to rebook
4. If they accept: creates a new appointment via `POST /appointments`

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `ACUITY_USER_ID` | Acuity numeric User ID |
| `ACUITY_API_KEY` | Acuity API Key |

## Usage

```bash
python -m examples.integrations.acuity_scheduling.no_show_followup "+15551234567" --name "Alex Rivera" --appointment-id "987654321" --rebook-date "2026-04-05"
```
