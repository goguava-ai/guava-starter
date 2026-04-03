# Tag and Assign

**Direction:** Inbound

Triages an inbound call, creates a Front conversation, applies category and urgency tags, and assigns it to the right teammate based on configurable routing rules.

## What it does

1. Collects caller name, email, category, issue summary, and urgency
2. Creates a conversation in the Front inbox via `POST /channels/{inbox_id}/incoming_messages`
3. Creates or fetches tags via `GET /tags` / `POST /tags`, then applies them via `POST /conversations/{id}/tags`
4. Assigns the conversation to the configured teammate via `PATCH /conversations/{id}`

## Routing Map

| Category | Env Variable |
|---|---|
| Billing | `FRONT_TEAMMATE_BILLING` |
| Technical Support | `FRONT_TEAMMATE_TECH` |
| Account Management | `FRONT_TEAMMATE_AM` |
| Sales | `FRONT_TEAMMATE_SALES` |
| General | `FRONT_TEAMMATE_GENERAL` |

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `FRONT_API_TOKEN` | Front API token |
| `FRONT_INBOX_ID` | Front inbox ID |
| `FRONT_TEAMMATE_*` | Teammate IDs for each routing category |

## Usage

```bash
python __main__.py
```
