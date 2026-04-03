# Outbound Re-engagement

**Direction:** Outbound

Call lapsed Intercom users to understand why they churned and gauge re-engagement interest. The outcome is captured as custom attributes and tags on the contact.

## What it does

1. Fetches contact details pre-call via `GET /contacts/{id}` (last seen date, email)
2. Calls the contact and conducts a re-engagement conversation
3. Tags the contact with the outcome (e.g. `re-engaged`, `demo-requested`, `churned-confirmed`)
4. Updates custom attributes `reengagement_outcome` and `reengagement_date` via `PUT /contacts/{id}`

## Outcome Tags

| Outcome | Tag Applied |
|---|---|
| Interested in returning | `re-engaged` |
| Needs pricing info | `pricing-requested` |
| Wants a demo | `demo-requested` |
| Churned permanently | `churned-confirmed` |
| Not interested | `not-interested` |

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `INTERCOM_ACCESS_TOKEN` | Intercom Access Token |

## Usage

```bash
python __main__.py +15551234567 --contact-id "cont_XXXX" --name "Jane Smith"
```
