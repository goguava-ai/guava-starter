# Preference Update

**Direction:** Inbound

A customer calls to update their notification and communication preferences. The agent verifies their identity by email, collects their choices, and applies them as a targeted `$set` on the `preferences` subdocument.

## Document Shape

```json
{
  "email": "jane@acme.com",
  "name": "Jane Smith",
  "preferences": {
    "marketing_emails": false,
    "sms_notifications": true,
    "weekly_digest": true,
    "contact_frequency": "quarterly",
    "updated_at": "2026-03-26T14:22:00Z"
  }
}
```

## Collection

`customers`

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `MONGODB_URI` | MongoDB Atlas connection string |
| `MONGODB_DATABASE` | Database name |

## Usage

```bash
python __main__.py
```
