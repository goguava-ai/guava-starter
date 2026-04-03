# Email Follow-Up

**Direction:** Outbound

When an important email needs a response, this agent proactively calls the contact to follow up. Before the call, it fetches the email subject and preview from the sender's mailbox so the agent can reference the email naturally. After the conversation, it marks the email as read and flags it if follow-up is still needed.

## What it does

1. Fetches the email pre-call via `GET /users/{userId}/messages/{messageId}` — captures subject, preview, and received date
2. Calls the contact via `reach_person`; if they're unavailable, leaves a professional voicemail referencing the email subject
3. Asks if they received and reviewed the email, then collects their response or timeline
4. Marks the message as read via `PATCH /users/{userId}/messages/{messageId}` with `isRead: true`
5. Flags the message for re-follow-up if they haven't reviewed it yet

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `GRAPH_ACCESS_TOKEN` | Microsoft Graph OAuth 2.0 access token |

## Usage

```bash
python -m examples.integrations.outlook.email_follow_up \
  "+15551234567" \
  --name "Jane Smith" \
  --user-id me@company.com \
  --message-id AAMkAGI2...
```
