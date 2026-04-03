# Shipping Delay Notification

**Direction:** Outbound

Proactively calls customers whose orders are delayed, explains the situation, provides an updated estimated delivery date, and lets the customer choose how to proceed.

## What it does

1. Pre-fetches the order from ShipStation before placing the call
2. Reaches the customer by name; leaves a voicemail with delay details if unavailable
3. Explains the delay reason and provides both the original and updated estimated delivery dates
4. Offers three resolution options: wait for the updated delivery, cancel for a full refund, or expedite at no charge
5. Collects any additional concerns from the customer
6. Executes the chosen action in ShipStation:
   - **Cancel:** calls `DELETE /orders/{orderId}` to cancel the order
   - **Expedite:** calls `PUT /orders/holdorder` to flag the order for the fulfillment team to upgrade shipping
   - **Wait:** no order change needed
7. Appends a structured note with the outcome to the order via `POST /orders/createorder`

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `SHIPSTATION_API_KEY` | ShipStation API key |
| `SHIPSTATION_API_SECRET` | ShipStation API secret |

## Usage

```bash
python __main__.py +15551234567 \
  --order-number 10087 \
  --name "Taylor Nguyen" \
  --delay-reason "severe weather affecting the carrier network" \
  --original-delivery-date "March 28" \
  --updated-delivery-date "April 2"
```
