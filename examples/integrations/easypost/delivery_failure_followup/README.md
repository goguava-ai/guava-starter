# Delivery Failure Follow-up

**Direction:** Outbound

Calls customers whose package shows a `failure` or `return_to_sender` status, explains the situation, collects a corrected shipping address, verifies it via EasyPost, and offers either a reship or a full refund.

## What it does

1. Pre-fetches the tracker via GET /trackers before the call begins
2. Dials the customer and identifies the caller as Summit Outfitters
3. Explains the delivery issue and asks whether the customer was aware
4. Collects a corrected street address, city, state, and ZIP code
5. Asks whether the customer prefers a reship or a full refund
6. If reshipping: verifies the new address via POST /addresses with delivery verification
7. Closes the call confirming the chosen resolution; leaves a voicemail if the customer is unavailable

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `EASYPOST_API_KEY` | EasyPost API key (test or production) |

## Usage

```bash
python __main__.py +15551234567 --tracking-code EZ1000000001 --name "Jane Smith" --order-number ORD-9821
```
