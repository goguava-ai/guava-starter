# Schedule Change Request — Calabrio Integration

An inbound voice agent that allows contact center agents to submit schedule change requests — including time off, shift swaps, start time changes, and early release requests — by calling in.

## How It Works

**1. Collect request details**

The agent gathers the caller's email, request type, target date, reason, and any additional details (e.g. swap partner name or preferred start time).

**2. Look up the agent in Calabrio**

`find_agent_by_email()` fetches the agent profile and internal ID needed to submit the request.

**3. Submit the request**

`submit_schedule_change_request()` posts to `POST /api/scheduling/requests` with the request type mapped to Calabrio's internal type codes (`TimeOff`, `ShiftSwap`, `StartTimeChange`, `EarlyRelease`).

**4. Confirm with the caller**

The agent confirms the request was submitted, provides the request ID, and lets the caller know their supervisor will respond within one business day.

## Calabrio API Calls

| Timing | Method | Endpoint | Purpose |
|---|---|---|---|
| Mid-call | `GET` | `/api/agents?email={email}` | Look up agent by email |
| Post-collect | `POST` | `/api/scheduling/requests` | Submit schedule change request |

## Setup

```bash
export GUAVA_AGENT_NUMBER="+1..."
export CALABRIO_BASE_URL="https://mycompany.calabriocloud.com"
export CALABRIO_API_KEY="..."
```

## Run

```bash
python -m examples.integrations.calabrio.schedule_change_request
```
