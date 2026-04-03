# Shipment Tracking

**Direction:** Inbound

Customer calls to check the status of their shipment; the agent looks up the tracking number via EasyPost and reports the current status, last known location, and estimated delivery date.

## What it does

1. Greets the caller and asks for their tracking number
2. Optionally asks which carrier shipped the package
3. Queries GET /trackers with the tracking code and optional carrier filter
4. Reports shipment status, last known location, and estimated delivery date
5. Tailors the closing message to the specific status (in transit, delivered, failure, etc.)

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `EASYPOST_API_KEY` | EasyPost API key (test or production) |

## Usage

```bash
python __main__.py
```
