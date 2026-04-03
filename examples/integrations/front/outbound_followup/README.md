# Outbound Followup

**Direction:** Outbound

Follow up with a customer by phone on a pending Front conversation. The outcome is logged as a comment and the conversation is archived if resolved.

## What it does

1. Fetches the conversation subject pre-call via `GET /conversations/{id}`
2. Calls the contact and determines if the issue has been resolved
3. Adds a comment via `POST /conversations/{id}/comments`
4. Archives the conversation via `PATCH /conversations/{id}` if the customer confirms it's resolved

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `FRONT_API_TOKEN` | Front API token |

## Usage

```bash
python __main__.py +15551234567 \
  --name "Jane Smith" \
  --conversation-id "cnv_XXXX" \
  --author-id "tea_XXXX"
```
