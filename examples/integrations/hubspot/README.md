# HubSpot CRM Integration

Voice agents that integrate with the [HubSpot CRM API](https://developers.hubspot.com/docs/api/crm/contacts) to capture leads, qualify prospects, keep contact records current, and follow up with customers — all without manual data entry.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`lead_capture`](lead_capture/) | Inbound | New prospect calls; agent collects contact info and opens a deal in HubSpot |
| [`contact_lookup`](contact_lookup/) | Inbound | Customer calls to check their account details; agent looks up their HubSpot record |
| [`deal_qualification`](deal_qualification/) | Inbound | Inbound prospect is walked through BANT qualification; contact and deal are created |
| [`contact_update`](contact_update/) | Inbound | Customer calls to update their phone, title, company, or email in HubSpot |
| [`renewal_outreach`](renewal_outreach/) | Outbound | Proactively call customers approaching contract renewal; capture intent and update deal stage |
| [`win_loss_survey`](win_loss_survey/) | Outbound | Call contacts on closed deals to gather win/loss feedback; log results as a note |
| [`meeting_followup`](meeting_followup/) | Outbound | Follow up after a demo or meeting; capture next steps and log a call note on the contact |

## Authentication

All examples use HubSpot Private App access tokens:

```
Authorization: Bearer {HUBSPOT_ACCESS_TOKEN}
```

Create a private app in HubSpot: **Settings** → **Integrations** → **Private Apps** → **Create a private app**. Grant scopes for `crm.objects.contacts.read`, `crm.objects.contacts.write`, `crm.objects.deals.read`, `crm.objects.deals.write`, and `crm.objects.notes.write`.

## Common Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `HUBSPOT_ACCESS_TOKEN` | HubSpot private app access token |

## HubSpot API Reference

- [Contacts](https://developers.hubspot.com/docs/api/crm/contacts)
- [Deals](https://developers.hubspot.com/docs/api/crm/deals)
- [Notes](https://developers.hubspot.com/docs/api/crm/notes)
- [Search](https://developers.hubspot.com/docs/api/crm/search)
- [Associations](https://developers.hubspot.com/docs/api/crm/associations)
