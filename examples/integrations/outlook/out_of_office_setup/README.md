# Out-of-Office Setup

**Direction:** Inbound

A team member calls to configure their Outlook out-of-office auto-reply before going on leave, or to turn off an existing one when they return. The agent collects the dates, backup contact, and an optional custom message, then activates or disables the setting.

## What it does

1. Asks whether to set up or turn off the auto-reply
2. **Set up:** collects start date, end date, backup contact, and optional custom message; calls `PATCH /me/mailboxSettings` with `automaticRepliesSetting.status = "scheduled"` and the date range
3. **Turn off:** calls `PATCH /me/mailboxSettings` with `automaticRepliesSetting.status = "disabled"`
4. If no custom message is provided, uses a standard Meridian Partners template populated with the return date and backup contact

Both internal (within-org) and external (outside-org) reply messages are set.

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `GRAPH_ACCESS_TOKEN` | Microsoft Graph OAuth 2.0 access token |
| `GRAPH_TIMEZONE` | Windows timezone name (default: `Eastern Standard Time`) |

## Usage

```bash
python -m examples.integrations.outlook.out_of_office_setup
```
