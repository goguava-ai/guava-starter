# Zapier Integration

Voice agents that integrate with [Zapier Webhooks (Catch Hooks)](https://zapier.com/apps/webhook/integrations) to trigger multi-step automation workflows from a voice call — connecting Guava to thousands of apps without custom API code.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`webhook_trigger`](webhook_trigger/) | Inbound | Collect caller details and fire a Zapier Catch Hook to trigger any downstream workflow |
| [`lead_routing`](lead_routing/) | Inbound | Qualify a sales lead and send structured data to Zapier for routing to the right CRM or rep |
| [`support_intake`](support_intake/) | Inbound | Capture a support issue and trigger a Zap to create tickets across multiple tools simultaneously |
| [`outbound_notify`](outbound_notify/) | Outbound | Deliver a notification to a contact and POST the call outcome back to Zapier for logging |

## How it works

Zapier's **Catch Hook** trigger accepts any HTTP POST with a JSON body. Each example POSTs a structured payload to `ZAPIER_WEBHOOK_URL` at the end of the call. From there, the Zap can:

- Create records in Salesforce, HubSpot, Airtable, Google Sheets, etc.
- Send Slack or email notifications
- Route leads to the right rep via round-robin logic
- Trigger multi-step sequences

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `ZAPIER_WEBHOOK_URL` | Zapier Catch Hook URL (from **Trigger → Webhooks by Zapier → Catch Hook**) |

## Usage

```bash
# Inbound examples
python __main__.py

# Outbound notify
python __main__.py +15551234567 --name "Jane Smith" --message "Your order has shipped." --campaign-id "camp_001"
```
