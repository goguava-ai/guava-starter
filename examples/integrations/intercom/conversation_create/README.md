# Conversation Create

**Direction:** Inbound

Logs a support call as an Intercom conversation. The agent finds or creates a contact, creates the conversation on their behalf, and adds an internal note with call metadata.

## What it does

1. Searches for an existing contact by email via `POST /contacts/search`
2. Creates a new contact via `POST /contacts` if not found (role: user)
3. Creates a conversation on behalf of the contact via `POST /conversations`
4. Adds an internal note with call source, type, and timestamp via `POST /conversations/{id}/parts`

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `INTERCOM_ACCESS_TOKEN` | Intercom Access Token |

## Usage

```bash
python __main__.py
```
