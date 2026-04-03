# Calabrio Integration

Voice agents that integrate with the [Calabrio ONE API](https://help.calabrio.com) to handle agent schedule inquiries, schedule change requests, post-call CSAT surveys, and quality evaluation coaching follow-ups — all over the phone.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`schedule_inquiry`](schedule_inquiry/) | Inbound | Agent calls to check their shift schedule for today, tomorrow, or a specific date |
| [`schedule_change_request`](schedule_change_request/) | Inbound | Agent calls to submit a time-off, shift swap, or start-time-change request |
| [`post_call_survey`](post_call_survey/) | Outbound | Agent calls customers after a contact to collect CSAT survey responses |
| [`post_evaluation_coaching`](post_evaluation_coaching/) | Outbound | QM team calls agents to deliver evaluation feedback and schedule coaching sessions |

## Authentication

All examples use an API key passed in the request header:

```
apiKey: {CALABRIO_API_KEY}
```

Generate an API key in Calabrio ONE: **Administration** → **API Keys** → **Create New Key**.

## Common Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `CALABRIO_BASE_URL` | Your Calabrio tenant URL (e.g. `https://mycompany.calabriocloud.com`) |
| `CALABRIO_API_KEY` | Calabrio REST API key |

## Calabrio REST API Reference

- [Agent Schedules](https://help.calabrio.com/Content/Developer/RESTfulAPI/RESTAPIOverview.htm)
- [Scheduling Requests](https://help.calabrio.com/Content/Developer/RESTfulAPI/RESTAPIOverview.htm)
- [Quality Management Evaluations](https://help.calabrio.com/Content/Developer/RESTfulAPI/RESTAPIOverview.htm)
- [Survey Responses](https://help.calabrio.com/Content/Developer/RESTfulAPI/RESTAPIOverview.htm)
