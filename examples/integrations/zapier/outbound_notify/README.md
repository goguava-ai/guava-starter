# Outbound Notify

**Direction:** Outbound

Deliver a notification message to a contact and POST the call outcome back to Zapier for logging. This is designed to be triggered by a Zapier workflow that supplies the contact list — closing the loop from a Zap into a voice call and back.

## What it does

1. Calls the contact and reads the notification message
2. Collects acknowledgment and whether they have questions or want to opt out
3. POSTs the outcome (`completed`, `voicemail`, opt-out flag) back to Zapier for downstream logging

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `ZAPIER_WEBHOOK_URL` | Zapier Catch Hook URL for outcome reporting |

## Usage

```bash
python __main__.py +15551234567 --name "Jane Smith" \
  --message "Your order has shipped and will arrive Thursday." \
  --campaign-id "camp_april_2024"
```
