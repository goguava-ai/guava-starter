# Lost Package Claim

**Direction:** Inbound

Customer calls to report a package that shows as delivered in the carrier's system but was never received; the agent verifies delivery status, collects claim details, and processes a shipping label refund.

## What it does

1. Greets the caller and collects their tracking number
2. Asks the customer to confirm their delivery address and whether they've checked nearby locations
3. Collects a description of the package contents for claim records
4. Asks whether the customer wants to proceed with a shipping label refund
5. Looks up the tracker via GET /trackers and confirms the delivery status
6. If the package shows delivered and the customer consents, finds the shipment and calls POST /shipments/{id}/refund
7. Closes the call with a status-appropriate message: refund confirmed, refund failed (manual follow-up), or package not yet delivered

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `EASYPOST_API_KEY` | EasyPost API key (test or production) |

## Usage

```bash
python __main__.py
```
