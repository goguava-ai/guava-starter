# Conversation Create

**Direction:** Inbound

A caller's inquiry is captured and created as a new Front conversation so the team can reply via email without losing the context from the voice call.

## What it does

1. Collects caller name, email, inquiry type, description, and urgency
2. Creates a new inbound message in the configured Front inbox via `POST /channels/{inbox_id}/incoming_messages`
3. Tags the conversation with `voice` and `guava`

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `FRONT_API_TOKEN` | Front API token |
| `FRONT_INBOX_ID` | Front inbox ID (e.g. `inb_XXXX`) |

## Usage

```bash
python __main__.py
```
