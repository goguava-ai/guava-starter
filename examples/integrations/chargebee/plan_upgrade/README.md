# Plan Upgrade

**Direction:** Inbound

A customer calls to upgrade their Chargebee subscription to a higher-tier plan. The agent lists available plans, confirms the upgrade, and changes the plan via the Chargebee API.

## What it does

1. Pre-loads available plans via `GET /api/v2/plans`
2. Collects the subscription ID and desired plan
3. Matches the desired plan name to a Chargebee plan ID
4. Changes the plan via `POST /api/v2/subscriptions/{id}` with `plan_id` parameter

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `CHARGEBEE_SITE` | Chargebee site subdomain |
| `CHARGEBEE_API_KEY` | Chargebee API key |

## Usage

```bash
python -m examples.integrations.chargebee.plan_upgrade
```
