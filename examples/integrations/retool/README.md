# Retool Integration

Voice agents that integrate with [Retool Workflows](https://docs.retool.com/workflows) to trigger internal automation, submit helpdesk requests, and log call outcomes into Retool-backed applications — connecting voice to your internal tooling layer.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`it_helpdesk_request`](it_helpdesk_request/) | Inbound | Employee calls IT helpdesk; agent collects issue details and triggers a Retool workflow to create a ticket |
| [`workflow_trigger`](workflow_trigger/) | Inbound | Inbound call triggers a parameterized Retool workflow and reads back the result |
| [`employee_onboarding_check`](employee_onboarding_check/) | Outbound | Agent calls a new hire to verify their onboarding checklist items and updates Retool |

## Authentication

Retool Workflow webhooks use an API key passed as a header:

```
X-Workflow-Api-Key: YOUR_WORKFLOW_API_KEY
```

Get the webhook URL and API key in the Retool Workflow editor: open the **Trigger** block, select **Run from API**, and copy the webhook URL and generated key.

## Common Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `RETOOL_WORKFLOW_WEBHOOK_URL` | Webhook URL for the target workflow (from the Trigger block) |
| `RETOOL_WORKFLOW_API_KEY` | API key shown in the Retool workflow Trigger block |

## Retool Reference

- [Workflows Overview](https://docs.retool.com/workflows)
- [Triggering Workflows via API](https://docs.retool.com/workflows/guides/trigger)
- [Workflow Blocks Reference](https://docs.retool.com/workflows/reference/blocks)
