# Order Tracking

**Direction:** Inbound

Customer calls in to check the status of their order and get carrier and tracking information.

## What it does

1. Greets the caller as Ridgeline Sports agent Jordan
2. Asks whether the customer wants to look up by order number or email address
3. Collects the order number or email from the caller
4. Queries `GET /orders` to retrieve the order and its status
5. Queries `GET /shipments` to retrieve carrier code, tracking number, and ship date
6. Reads back the order status, carrier, and tracking number in plain language

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `SHIPSTATION_API_KEY` | ShipStation API key |
| `SHIPSTATION_API_SECRET` | ShipStation API secret |

## Usage

```bash
python __main__.py
```
