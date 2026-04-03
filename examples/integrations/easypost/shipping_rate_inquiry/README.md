# Shipping Rate Inquiry

**Direction:** Inbound

Customer calls to get a shipping rate quote before sending a package; the agent collects origin/destination addresses and package dimensions, creates an EasyPost shipment to retrieve live rates, and quotes the cheapest and fastest options.

## What it does

1. Greets the caller and collects the full origin address (street, city, state, ZIP)
2. Collects the full destination address
3. Collects package dimensions (length, width, height in inches) and weight in ounces
4. Creates a shipment via POST /shipments — this returns live carrier rates without purchasing a label
5. Identifies the cheapest and fastest rates from the response
6. Quotes both options to the caller with carrier, service level, price, and estimated transit days

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `EASYPOST_API_KEY` | EasyPost API key (test or production) |

## Usage

```bash
python __main__.py
```
