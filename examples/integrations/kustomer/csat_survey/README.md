# CSAT Survey — Kustomer Integration

An outbound voice agent that calls customers after a support case is resolved to collect a customer satisfaction (CSAT) rating. Survey results are written back to the Kustomer conversation as an internal note, and the conversation is tagged with `csat-collected` for easy tracking.

## How It Works

**1. Pre-call: fetch the conversation**

Before placing the call, `GET /conversations/{id}` retrieves the conversation preview or subject. This lets the agent reference the specific issue by name instead of a generic phrase, making the survey feel more personal.

**2. Reach the customer**

`reach_person()` places the outbound call and waits for a live person to answer. If the call goes to voicemail, `on_failure` leaves a brief, non-intrusive message and hangs up.

**3. Collect feedback**

The agent asks three questions:
- **Satisfaction rating**: 1–5 scale (1 = very dissatisfied, 5 = very satisfied)
- **Resolution quality**: whether the issue was fully resolved, partially resolved, or not resolved
- **Open feedback**: any additional comments (optional)

**4. Write results back to Kustomer**

`POST /conversations/{id}/notes` posts a private internal note with the full survey results and timestamp. Internal notes are visible only to agents in Kustomer — they do not trigger customer-facing notifications.

**5. Tag the conversation**

`PATCH /conversations/{id}` adds the `csat-collected` tag (along with `guava` and `voice`) so the conversation can be filtered in Kustomer reporting views.

**6. Close appropriately**

If the rating is 1 or 2, the agent acknowledges the poor experience and promises a personal follow-up. Higher ratings get a warm thank-you.

## Kustomer API Calls

| Timing | Endpoint | Purpose |
|---|---|---|
| Pre-call | `GET /conversations/{id}` | Fetch conversation details to personalize the survey |
| Post-survey | `POST /conversations/{id}/notes` | Add an internal note with CSAT results |
| Post-survey | `PATCH /conversations/{id}` | Tag the conversation as `csat-collected` |

## Setup

### 1. Get a Kustomer API token

In Kustomer: **Settings** → **Security** → **API Keys** → **Add API Key**. Grant the key `org.permission.conversation.read`, `org.permission.conversation.write`, and `org.permission.note.create` permissions.

### 2. Install dependencies

```bash
pip install guava requests
```

### 3. Set environment variables

```bash
export GUAVA_AGENT_NUMBER="+1..."
export KUSTOMER_API_TOKEN="<your_api_token>"
```

### 4. Run

```bash
python -m examples.integrations.kustomer.csat_survey +15551234567 \
  --conv-id abc123def456 \
  --name "Jane Smith"
```

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `KUSTOMER_API_TOKEN` | Kustomer API token |

## Arguments

| Argument | Description |
|---|---|
| `phone` | Customer phone number in E.164 format (e.g. `+15551234567`) |
| `--conv-id` | The resolved Kustomer conversation ID |
| `--name` | Customer's full name |
