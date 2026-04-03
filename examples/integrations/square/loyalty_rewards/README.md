# Loyalty Rewards

**Direction:** Inbound

A customer calls to check their Square loyalty points balance and reward status. The agent looks up their account by phone number and reads back their points, available rewards, and progress toward the next tier.

## What it does

1. Collects the customer's loyalty-linked phone number
2. Searches for their loyalty account via `POST /v2/loyalty/accounts/search` (phone mapping)
3. Fetches program reward tiers via `GET /v2/loyalty/programs/main`
4. Reads back current balance, lifetime points, available rewards, and points needed for the next tier

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `SQUARE_ACCESS_TOKEN` | Square access token |
| `SQUARE_BASE_URL` | `https://connect.squareupsandbox.com` or `https://connect.squareup.com` |

## Usage

```bash
python -m examples.integrations.square.loyalty_rewards
```
