# Return Authorization

**Direction:** Inbound

Customer calls to start a return on an order — the agent verifies eligibility against a 30-day return window, then creates a prepaid return shipping label via the ShipStation API.

## What it does

1. Greets the caller as Ridgeline Sports agent Alex
2. Collects the order number and reason for return
3. Looks up the order via `GET /orders` to confirm it exists and is in a returnable state
4. Checks that the order falls within the 30-day return window
5. Creates a prepaid return label via `POST /shipments/createlabel` with `isReturnLabel: true`
6. Records the return reason and return tracking number in the order's internal notes via `POST /orders/createorder`
7. Reads back the return tracking number and refund timeline to the caller

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `SHIPSTATION_API_KEY` | ShipStation API key |
| `SHIPSTATION_API_SECRET` | ShipStation API secret |
| `SHIPSTATION_WAREHOUSE_ID` | (Optional) Your ShipStation warehouse ID for return routing |

## Usage

```bash
python __main__.py
```
