# Return Initiation — ShipStation Integration

**Direction:** Inbound

An inbound voice agent that walks customers through starting a return. It collects their order details and return preferences, verifies the order is in a returnable status, and generates a prepaid return label via the ShipStation API — giving the customer their return tracking number before the call ends. If label creation fails, it escalates gracefully by promising the returns team will email a label within 1 business day.

## What it does

1. Greets the caller and collects their order number (or email as a fallback), their reason for returning, and their preferred resolution (full refund, exchange, or store credit).
2. Looks up the order in ShipStation and verifies it is in a `shipped` or `delivered` status — the only statuses eligible for a return. Orders that are awaiting shipment, on hold, or cancelled are handled with an appropriate explanation.
3. Fetches the original shipment to reuse the carrier and service code for the return label, defaulting to UPS Ground if no shipment is found.
4. Calls `POST /shipments/createlabel` with `isReturnLabel: true` to generate a prepaid return label.
5. Reads the return tracking number back to the customer and explains what to expect based on their chosen resolution.
6. If label creation fails, escalates to the returns team with a 1 business day email commitment.

## ShipStation API Calls

| Timing | Method | Endpoint | Purpose |
|---|---|---|---|
| Post-collection | `GET` | `/orders?orderNumber=<n>` | Find and verify the order |
| Post-collection | `GET` | `/orders?customerEmail=<e>&orderStatus=shipped` | Find shipped orders by email (fallback) |
| Post-verification | `GET` | `/shipments?orderId=<id>` | Get original carrier and service code |
| Post-verification | `POST` | `/shipments/createlabel` | Generate the prepaid return label |

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `SHIPSTATION_API_KEY` | ShipStation API key |
| `SHIPSTATION_API_SECRET` | ShipStation API secret |

## Usage

```bash
python -m examples.integrations.shipstation.return_initiation
```
