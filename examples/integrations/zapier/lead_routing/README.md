# Lead Routing

**Direction:** Inbound

A prospect calls and the agent qualifies them with BANT-style questions. The collected data — including a computed routing tier (enterprise, mid-market, or SMB) — is sent to Zapier to route the lead to the appropriate CRM and sales rep.

## What it does

1. Collects name, email, company, use case, budget, timeline, and company size
2. Computes a `routing_tier` (enterprise / mid_market / smb) based on budget × timeline
3. POSTs the payload to Zapier for CRM entry and rep assignment

## Tier Mapping

| Budget | Timeline | Tier |
|---|---|---|
| Over $100k | Immediately or 1–3 months | Enterprise |
| $25k–$100k | Immediately through 3–6 months | Mid-Market |
| All others | — | SMB |

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `ZAPIER_WEBHOOK_URL` | Zapier Catch Hook URL |

## Usage

```bash
python __main__.py
```
