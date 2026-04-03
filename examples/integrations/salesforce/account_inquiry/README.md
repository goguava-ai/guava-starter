# Account Inquiry

**Direction:** Inbound

A caller (account manager or customer) asks for a summary of a Salesforce account. The agent queries the Account record, counts open Cases, and lists active Opportunities — then delivers a conversational summary.

## What it does

1. Asks for the account name and what type of information is needed
2. Finds the Account via SOQL `GET /query` (name fuzzy match)
3. Optionally fetches open Case count via `SELECT COUNT() FROM Case`
4. Optionally fetches active Opportunities via `SELECT ... FROM Opportunity`
5. Delivers a natural-language summary and ends the call

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
