# Webhook Trigger

**Direction:** Inbound

A caller provides their contact details and request type. At the end of the call the agent POSTs a structured JSON payload to a Zapier Catch Hook, triggering any connected Zap — CRM entry, Slack notification, email, spreadsheet update, and more.

## What it does

1. Collects caller name, email, request type, description, and follow-up preference
2. POSTs a structured JSON payload to `ZAPIER_WEBHOOK_URL` via `POST` (Zapier Catch Hook)
3. The Zap can then route to any of Zapier's 6,000+ connected apps

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `ZAPIER_WEBHOOK_URL` | Zapier Catch Hook URL |

## Usage

```bash
python __main__.py
```
