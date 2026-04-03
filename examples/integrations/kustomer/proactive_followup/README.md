# Proactive Follow-Up — Kustomer Integration

An outbound voice agent that proactively calls customers to follow up on open support conversations that haven't been updated in a while. Based on the outcome, the agent either closes the case, schedules a callback, or queues an email follow-up — and records the result as an internal note.

## How It Works

**1. Pre-call: fetch the conversation**

Before placing the call, `GET /conversations/{id}` retrieves the conversation preview and current status. This gives the agent context to reference the specific issue by name during the call.

**2. Reach the customer**

`reach_person()` places the outbound call and waits for a live person to answer. If the call goes to voicemail, `on_failure` leaves a brief message and records a follow-up attempt note on the conversation.

**3. Check in on the issue**

The agent asks three questions:
- **Issue resolved**: yes (fully resolved), partially (some problems remain), or no (still ongoing)
- **Additional help needed**: any new information or requests (optional)
- **Preferred next step**: email follow-up, callback from a support agent, or close the case

**4. Act on the outcome**

- **Close case**: `PATCH /conversations/{id}` sets the conversation status to `done`. A closing note is added and the caller is informed their case is closed.
- **Callback or email**: The conversation remains open. A follow-up note is added and the caller is told what to expect next.

**5. Record the call**

`POST /conversations/{id}/notes` adds an internal note with the follow-up timestamp, resolution status, and preferred next step — keeping the conversation history complete.

## Kustomer API Calls

| Timing | Endpoint | Purpose |
|---|---|---|
| Pre-call | `GET /conversations/{id}` | Fetch conversation context for the follow-up |
| Post-call | `PATCH /conversations/{id}` | Close the conversation if customer requests it |
| Post-call | `POST /conversations/{id}/notes` | Record follow-up outcome as an internal note |

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
python -m examples.integrations.kustomer.proactive_followup +15551234567 \
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
| `--conv-id` | The Kustomer conversation ID to follow up on |
| `--name` | Customer's full name |
