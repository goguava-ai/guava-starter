# Availability Check

**Direction:** Inbound

A caller wants to know the next available appointment time. The agent collects their service type and preferred timeframe, searches across 14 days for availability matching their preference, and reads back the next open slot.

## What it does

1. Pre-loads appointment types via `GET /appointment-types`
2. Collects service type, preferred week, and morning/afternoon preference
3. Iterates `GET /availability/times` day-by-day for up to 14 days to find the first matching slot
4. Reads back the next available time and invites them to book online or call back

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `ACUITY_USER_ID` | Acuity numeric User ID |
| `ACUITY_API_KEY` | Acuity API Key |
| `ACUITY_APPOINTMENT_TYPE_ID` | Default appointment type ID (fallback) |

## Usage

```bash
python -m examples.integrations.acuity_scheduling.availability_check
```
