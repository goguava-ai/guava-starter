# Shipment Tracking — ShipStation Integration

**Direction:** Inbound

An inbound voice agent that answers when a customer calls to track their shipment. It collects their order number or email address, looks up the order and shipment in ShipStation, reads back the tracking number and carrier, and gives them a direct tracking URL — all within the call.

## What it does

1. Greets the caller and asks for their order number. If they don't have it, accepts their email address instead.
2. Looks up the order in ShipStation using `GET /orders?orderNumber=<orderNumber>` or `GET /orders?customerEmail=<email>&orderStatus=shipped`.
3. Fetches the associated shipment using `GET /shipments?orderId=<orderId>` to retrieve the tracking number, carrier, and ship date.
4. Maps the order status to a human-readable phrase (e.g., "awaiting shipment" → "your order is being prepared for shipment").
5. Reads back the carrier, ship date, tracking number, and a direct tracking URL based on the carrier code.
6. Asks if the customer needs anything else (report a problem, start a return, or nothing) and closes appropriately.

## ShipStation API Calls

| Timing | Method | Endpoint | Purpose |
|---|---|---|---|
| Post-collection | `GET` | `/orders?orderNumber=<n>` | Find the order by order number |
| Post-collection | `GET` | `/orders?customerEmail=<e>&orderStatus=shipped` | Find shipped orders by email (fallback) |
| Post-lookup | `GET` | `/shipments?orderId=<id>` | Get tracking details for the order |

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `SHIPSTATION_API_KEY` | ShipStation API key |
| `SHIPSTATION_API_SECRET` | ShipStation API secret |

## Usage

```bash
python -m examples.integrations.shipstation.shipment_tracking
```
