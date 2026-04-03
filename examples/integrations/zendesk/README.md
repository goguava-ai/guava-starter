# Zendesk Support Integration

Voice agents that integrate with the [Zendesk Support API](https://developer.zendesk.com/api-reference/ticketing/introduction/) to handle inbound support calls, proactively reach customers, and keep ticket records up to date — all without manual agent intervention.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`ticket_creation`](ticket_creation/) | Inbound | Customer calls to report an issue; agent creates a Zendesk ticket |
| [`ticket_status_check`](ticket_status_check/) | Inbound | Customer calls to check their ticket status by ID or email |
| [`ticket_update`](ticket_update/) | Inbound | Customer calls to add information to an open ticket |
| [`escalation`](escalation/) | Inbound | Triage call creates an urgent incident assigned to a senior support group |
| [`user_registration`](user_registration/) | Inbound | New customer is registered in Zendesk and their first ticket is opened |
| [`csat_survey`](csat_survey/) | Outbound | Post-resolution satisfaction survey; results written back to the ticket |
| [`proactive_update`](proactive_update/) | Outbound | Deliver a specific ticket update to a customer and log the call outcome |
| [`outbound_outage_notify`](outbound_outage_notify/) | Outbound | Call all customers with open incident tickets linked to a problem ticket |

## Authentication

All examples use Zendesk API token authentication:

```
Authorization: Basic base64("{email}/token:{api_token}")
```

Get an API token in Zendesk: **Admin Center** → **Apps and Integrations** → **APIs** → **Zendesk API** → **Add API token**.

## Common Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `ZENDESK_SUBDOMAIN` | Your Zendesk subdomain (e.g. `yourcompany` for `yourcompany.zendesk.com`) |
| `ZENDESK_EMAIL` | Email of the Zendesk agent account used to authenticate |
| `ZENDESK_API_TOKEN` | Zendesk API token |

## Zendesk API Reference

- [Tickets](https://developer.zendesk.com/api-reference/ticketing/tickets/tickets/)
- [Users](https://developer.zendesk.com/api-reference/ticketing/users/users/)
- [Ticket Comments](https://developer.zendesk.com/api-reference/ticketing/tickets/ticket_comments/)
