# Shipping Issue — ShipStation Integration

**Direction:** Inbound

An inbound voice agent that handles calls from customers reporting problems with their shipment. It collects the issue type, looks up the order and shipment in ShipStation, and routes to the appropriate collection flow — gathering claim details for lost or damaged packages, providing tracking info for delays, or capturing the discrepancy for wrong-item reports.

## What it does

1. Greets the caller and collects their order number (or email as a fallback) and the type of issue they are experiencing: lost, damaged, delayed, or wrong items received.
2. Looks up the order in ShipStation and fetches the associated shipment for tracking context.
3. Routes the call based on the issue type:
   - **Lost or damaged:** Collects a description of what happened and the customer's preferred resolution (replacement shipment, full refund, or store credit). Closes with a promise that the claims team will follow up within 1 business day.
   - **Delayed:** Reads back the carrier, ship date, and tracking URL so the customer can monitor progress. Advises them to call back if the package doesn't arrive within 2 more business days.
   - **Wrong items received:** Collects a description of what was received versus what was ordered. Closes with confirmation that the correct replacement will be dispatched within 1 business day.

## ShipStation API Calls

| Timing | Method | Endpoint | Purpose |
|---|---|---|---|
| Post-collection | `GET` | `/orders?orderNumber=<n>` | Find the order by order number |
| Post-collection | `GET` | `/orders?customerEmail=<e>&orderStatus=shipped` | Find shipped orders by email (fallback) |
| Post-lookup | `GET` | `/shipments?orderId=<id>` | Get carrier and tracking details |

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `SHIPSTATION_API_KEY` | ShipStation API key |
| `SHIPSTATION_API_SECRET` | ShipStation API secret |

## Usage

```bash
python -m examples.integrations.shipstation.shipping_issue
```
