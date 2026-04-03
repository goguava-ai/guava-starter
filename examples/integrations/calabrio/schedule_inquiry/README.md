# Schedule Inquiry — Calabrio Integration

An inbound voice agent that allows contact center agents to check their upcoming work schedules by calling in. Agents identify themselves by email and request their schedule for today, tomorrow, or a specific date.

## How It Works

**1. Collect agent identity and date preference**

The agent gathers the caller's work email and whether they want today's, tomorrow's, or a specific date's schedule.

**2. Look up the agent in Calabrio**

`find_agent_by_email()` calls `GET /api/agents?email={email}` to retrieve the agent's profile and internal ID.

**3. Fetch the schedule**

`get_agent_schedule()` calls `GET /api/agents/{id}/schedule?startDate={date}&endDate={date}` to get the day's scheduled activities.

**4. Read the schedule**

`format_shift()` formats each activity as "{activity name} from {start} to {end}". Multiple activities are read in sequence with "then" between them.

## Calabrio API Calls

| Timing | Method | Endpoint | Purpose |
|---|---|---|---|
| Mid-call | `GET` | `/api/agents?email={email}` | Look up agent by email |
| Mid-call | `GET` | `/api/agents/{id}/schedule` | Fetch agent schedule for date |

## Setup

```bash
export GUAVA_AGENT_NUMBER="+1..."
export CALABRIO_BASE_URL="https://mycompany.calabriocloud.com"
export CALABRIO_API_KEY="..."
```

## Run

```bash
python -m examples.integrations.calabrio.schedule_inquiry
```

## Sample Output

```json
{
  "use_case": "schedule_inquiry",
  "caller_email": "jane.doe@company.com",
  "date": "2026-03-31",
  "shifts_found": 2,
  "shifts": [
    {"activityName": "Inbound Calls", "startTime": "09:00", "endTime": "12:00"},
    {"activityName": "Lunch Break", "startTime": "12:00", "endTime": "13:00"}
  ]
}
```
