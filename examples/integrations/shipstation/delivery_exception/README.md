# Delivery Exception

**Direction:** Outbound

Calls customers whose shipment has encountered a delivery exception (failed delivery, address not found, access issue) to collect updated delivery instructions and log them on the order.

## What it does

1. Pre-fetches the shipment and order from ShipStation before placing the call
2. Reaches the customer by name; leaves a voicemail if unavailable
3. Explains the delivery exception reason and provides the tracking number
4. Collects the customer's preferred resolution: redeliver, update address, or hold for pickup
5. Collects any specific delivery instructions or a new address
6. Appends a structured note to the order's internal notes via `POST /orders/createorder`

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `SHIPSTATION_API_KEY` | ShipStation API key |
| `SHIPSTATION_API_SECRET` | ShipStation API secret |

## Usage

```bash
python __main__.py +15551234567 \
  --order-number 10045 \
  --name "Jamie Rivera" \
  --exception-reason "delivery attempted - no access to building"
```
