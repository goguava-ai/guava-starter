# Intercom Integration

Voice agents that integrate with the [Intercom REST API](https://developers.intercom.com/docs/build-an-integration/learn-more/rest-apis/) to look up customer profiles, create conversations, capture leads, and re-engage lapsed users — bringing voice touchpoints into the Intercom customer lifecycle.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`contact_lookup`](contact_lookup/) | Inbound | Look up a caller's Intercom profile by email before assisting — session count, plan, last seen |
| [`conversation_create`](conversation_create/) | Inbound | Log a support call as an Intercom conversation with an internal note for the team |
| [`lead_capture`](lead_capture/) | Inbound | Qualify an inbound prospect and create or update an Intercom lead with tags |
| [`outbound_reengagement`](outbound_reengagement/) | Outbound | Call lapsed users to understand why they churned and capture re-engagement intent |

## Authentication

All examples use an Intercom Access Token (Bearer authentication):

```python
HEADERS = {
    "Authorization": f"Bearer {INTERCOM_ACCESS_TOKEN}",
    "Intercom-Version": "2.10",
}
```

Generate a token at: **Settings → Integrations → Developer Hub → Your App → Authentication**.

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `INTERCOM_ACCESS_TOKEN` | Intercom Access Token |

## Intercom API Reference

- [Contacts](https://developers.intercom.com/docs/references/rest-api/api.intercom.io/Contacts/)
- [Conversations](https://developers.intercom.com/docs/references/rest-api/api.intercom.io/Conversations/)
- [Tags](https://developers.intercom.com/docs/references/rest-api/api.intercom.io/Tags/)
