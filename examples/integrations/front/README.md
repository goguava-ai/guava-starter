# Front Integration

Voice agents that integrate with the [Front API](https://dev.frontapp.com/) to create conversations, look up contact history, follow up on pending threads, and route inquiries to the right teammate — turning every voice call into a tracked Front conversation.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`conversation_create`](conversation_create/) | Inbound | Create a new Front conversation from an inbound call so the team can follow up via email |
| [`contact_lookup`](contact_lookup/) | Inbound | Look up a caller's Front contact and recent conversations before assisting them |
| [`outbound_followup`](outbound_followup/) | Outbound | Follow up on a pending Front conversation by phone; log the outcome as a comment |
| [`tag_and_assign`](tag_and_assign/) | Inbound | Triage an inbound call, create a conversation, apply category/urgency tags, and assign it to the right teammate |

## Authentication

All examples use a Front API token (Bearer authentication):

```python
HEADERS = {"Authorization": f"Bearer {FRONT_API_TOKEN}"}
```

Create a token at: **Settings → Developers → API Tokens** in Front.

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `FRONT_API_TOKEN` | Front API token |
| `FRONT_INBOX_ID` | Front channel/inbox ID to create conversations in (e.g. `inb_XXXX`) |
| `FRONT_TEAMMATE_BILLING` | *(tag_and_assign)* Teammate ID for billing routing |
| `FRONT_TEAMMATE_TECH` | *(tag_and_assign)* Teammate ID for technical support routing |
| `FRONT_TEAMMATE_AM` | *(tag_and_assign)* Teammate ID for account management routing |
| `FRONT_TEAMMATE_SALES` | *(tag_and_assign)* Teammate ID for sales routing |
| `FRONT_TEAMMATE_GENERAL` | *(tag_and_assign)* Teammate ID for general routing |

## Front API Reference

- [Conversations](https://dev.frontapp.com/reference/list-conversations)
- [Contacts](https://dev.frontapp.com/reference/list-contacts)
- [Channels / Incoming Messages](https://dev.frontapp.com/reference/create-channel-message)
- [Tags](https://dev.frontapp.com/reference/list-tags)
