# Zoho Desk Integration

Voice agents that integrate with the [Zoho Desk API](https://desk.zoho.com/DeskAPIDocument) to handle inbound support calls, survey customers after resolution, and keep ticket records up to date — all without manual agent intervention.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`ticket_creation`](ticket_creation/) | Inbound | Customer calls to report an issue; agent creates a Zoho Desk ticket |
| [`ticket_status`](ticket_status/) | Inbound | Customer calls to check their ticket status by ticket number or email |
| [`ticket_update`](ticket_update/) | Inbound | Customer calls to add information to an existing open ticket |
| [`escalation`](escalation/) | Inbound | Triage agent creates or upgrades a ticket to Urgent/Escalated with an internal note |
| [`csat_survey`](csat_survey/) | Outbound | Post-resolution satisfaction survey; results written back as an internal note |

## Authentication

Zoho Desk uses OAuth 2.0. All examples authenticate with a short-lived access token passed in the `Authorization` header:

```
Authorization: Zoho-oauthtoken {access_token}
```

**Generating a token:**

1. Go to [Zoho API Console](https://api-console.zoho.com/) and register a Self Client or Server-based OAuth application.
2. Grant the scopes your use case needs — at minimum `Desk.tickets.ALL` and `Desk.contacts.READ`.
3. Generate an authorization code and exchange it for an access token and refresh token.
4. Access tokens are short-lived (typically 1 hour). Use your refresh token to obtain a new access token before it expires. Refreshing tokens is outside the scope of these examples — the `ZOHO_DESK_ACCESS_TOKEN` environment variable is used as-is.

Your Zoho Desk **Organization ID** (`orgId`) is required as a header on every API call. Find it in Zoho Desk: **Setup** → **Developer Space** → **API** → copy the `orgId` value.

## Common Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `ZOHO_DESK_ACCESS_TOKEN` | Zoho OAuth 2.0 access token (short-lived; refresh before expiry) |
| `ZOHO_DESK_ORG_ID` | Your Zoho Desk organization ID |

## Zoho Desk API Reference

- [Tickets](https://desk.zoho.com/DeskAPIDocument#Tickets)
- [Ticket Comments](https://desk.zoho.com/DeskAPIDocument#TicketComments)
- [Contacts](https://desk.zoho.com/DeskAPIDocument#Contacts)
- [Authentication (OAuth)](https://desk.zoho.com/DeskAPIDocument#OauthTokens)
