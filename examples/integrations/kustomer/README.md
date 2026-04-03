# Kustomer CRM Integration

Voice agents that integrate with the [Kustomer API](https://developer.kustomer.com/kustomer-api-reference) to handle inbound support calls, proactively reach customers, and keep conversation records up to date — all without manual agent intervention.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`case_creation`](case_creation/) | Inbound | Customer calls to report an issue; agent looks up or creates the customer and opens a Kustomer conversation |
| [`customer_lookup`](customer_lookup/) | Inbound | Customer calls to look up their profile and recent case history by email or phone |
| [`case_update`](case_update/) | Inbound | Customer calls to add information to an existing open support case |
| [`csat_survey`](csat_survey/) | Outbound | Post-resolution satisfaction survey; results written back to the conversation as an internal note |
| [`proactive_followup`](proactive_followup/) | Outbound | Follow up on an open conversation that hasn't been updated recently; close or escalate based on outcome |

## Authentication

All examples use Kustomer API token (Bearer) authentication:

```
Authorization: Bearer {KUSTOMER_API_TOKEN}
```

Get an API token in Kustomer: **Settings** → **Security** → **API Keys** → **Add API Key**. Assign only the permissions required by each example (principle of least privilege).

## Common Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `KUSTOMER_API_TOKEN` | Kustomer API token |

## Kustomer API Reference

- [Customers](https://developer.kustomer.com/kustomer-api-reference/reference/getcustomers)
- [Conversations](https://developer.kustomer.com/kustomer-api-reference/reference/getconversations)
- [Messages](https://developer.kustomer.com/kustomer-api-reference/reference/getmessages)
- [Notes](https://developer.kustomer.com/kustomer-api-reference/reference/getnotes)
