# Freshdesk (Freshworks) Integration

Voice agents that integrate with the [Freshdesk API v2](https://developers.freshdesk.com/api/) to create support tickets, check ticket status, collect post-resolution CSAT feedback, and escalate tickets — all from a voice call.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`ticket_creation`](ticket_creation/) | Inbound | Customer calls with an issue; agent creates a Freshdesk ticket tagged and prioritized automatically |
| [`ticket_status`](ticket_status/) | Inbound | Customer calls to check their ticket status by ticket ID or email address |
| [`csat_survey`](csat_survey/) | Outbound | Follow up on a resolved ticket; collect a 1–5 CSAT rating and save it as a private note |
| [`escalation`](escalation/) | Inbound | Customer escalates an open ticket; agent bumps priority to Urgent and tags it for manager review |

## Authentication

Freshdesk uses HTTP Basic Authentication with the API key as the username and `"X"` as the password:

```python
AUTH = (FRESHDESK_API_KEY, "X")
requests.post(url, auth=AUTH, json=payload)
```

Find your API key at: **Profile Settings → Your API Key** in Freshdesk.

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `FRESHDESK_DOMAIN` | Your Freshdesk subdomain (e.g. `mycompany` → `mycompany.freshdesk.com`) |
| `FRESHDESK_API_KEY` | Your Freshdesk API key |

## Freshdesk API Reference

- [Tickets](https://developers.freshdesk.com/api/#tickets)
- [Notes](https://developers.freshdesk.com/api/#ticket_notes)
- [Contacts](https://developers.freshdesk.com/api/#contacts)
