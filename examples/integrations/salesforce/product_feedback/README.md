# Product Feedback

**Direction:** Inbound

Customers call to share product feedback, feature requests, or bug reports. The agent collects structured input and creates a Salesforce Case for tracking. Feature requests are also surfaced as a Chatter FeedItem on the Account.

## What it does

1. Looks up the caller's Contact by email via SOQL `GET /query`
2. Collects feedback type, product area, detailed description, and business impact
3. Creates a Case via `POST /sobjects/Case` (Type: Feature Request or Problem)
4. For feature requests, creates a Chatter FeedItem via `POST /sobjects/FeedItem` so the product team sees it in the account feed

## Case Type Mapping

| Feedback Type | Case Type |
|---|---|
| Feature request | Feature Request |
| Bug report / other | Problem |

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `SALESFORCE_INSTANCE_URL` | Your Salesforce org URL |
| `SALESFORCE_ACCESS_TOKEN` | OAuth2 Bearer token |

## Usage

```bash
python __main__.py
```
