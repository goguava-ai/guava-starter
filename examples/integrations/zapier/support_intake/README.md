# Support Intake

**Direction:** Inbound

A customer calls with a support issue. The agent collects structured triage data — product area, description, and impact level — then fires a Zapier webhook that can simultaneously create tickets in Zendesk, Jira, Slack, or any other connected tool.

## What it does

1. Collects caller details, product area, issue description, and impact level
2. Maps impact to a priority (urgent / high / normal / low)
3. POSTs the payload to Zapier, which can fan out to multiple ticketing systems at once

## Priority Mapping

| Impact | Priority |
|---|---|
| It stopped working entirely | Urgent |
| Major degradation | High |
| Minor issue, workaround exists | Normal |
| General question | Low |

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `ZAPIER_WEBHOOK_URL` | Zapier Catch Hook URL |

## Usage

```bash
python __main__.py
```
