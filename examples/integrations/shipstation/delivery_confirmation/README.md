# Delivery Confirmation — ShipStation Integration

**Direction:** Outbound

An outbound voice agent that calls customers after a shipment is marked delivered to confirm receipt and collect a satisfaction rating. Before placing the call, it fetches the shipment from ShipStation so it can provide the customer with tracking details if they haven't received the package yet. Responses drive a tailored closing — damaged packages escalate to the claims team, undelivered packages get tracking info, and satisfied customers are invited to leave a review.

## What it does

1. **Pre-call:** Fetches shipment details from `GET /shipments?shipmentId=<id>` to get the carrier code and tracking number. Builds a direct tracking URL in case the customer hasn't received the package.
2. **Reach the customer:** Uses `reach_person()` to connect to a live person. If no one answers, leaves a brief voicemail confirming the shipment and inviting them to call back with any issues.
3. **Confirm delivery:** Greets the customer and asks whether they received their order. Captures one of three states: received, not yet received, or damaged on arrival.
4. **Collect satisfaction (if received):** Asks for a satisfaction rating and whether they'd like to leave a review on the website.
5. **Close based on outcome:**
   - **Received + satisfied:** Thanks the customer and optionally directs them to the review page.
   - **Received + dissatisfied:** Acknowledges the poor experience and promises a personal follow-up.
   - **Not yet received:** Provides the tracking number, carrier, and tracking URL; advises them to call back if not received within 2 more days.
   - **Damaged:** Escalates immediately to the shipping claims team with a 1 business day follow-up commitment.

## ShipStation API Calls

| Timing | Method | Endpoint | Purpose |
|---|---|---|---|
| Pre-call | `GET` | `/shipments?shipmentId=<id>` | Fetch carrier and tracking info before placing the call |

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `SHIPSTATION_API_KEY` | ShipStation API key |
| `SHIPSTATION_API_SECRET` | ShipStation API secret |

## Usage

```bash
python -m examples.integrations.shipstation.delivery_confirmation +15551234567 \
  --name "Jane Smith" \
  --order-number "CS-10042" \
  --shipment-id 98765
```

## Arguments

| Argument | Description |
|---|---|
| `phone` | Customer phone number in E.164 format (e.g. `+15551234567`) |
| `--name` | Customer's full name |
| `--order-number` | ShipStation order number |
| `--shipment-id` | ShipStation shipment ID (integer) |
