# EasyPost Integration

Voice agents that integrate with the [EasyPost API](https://www.easypost.com/docs/api) to handle shipment tracking, lost package claims, delivery failure resolution, and shipping rate inquiries.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`shipment_tracking`](shipment_tracking/) | Inbound | Customer calls to check on their shipment status, location, and estimated delivery date |
| [`lost_package_claim`](lost_package_claim/) | Inbound | Customer reports a package that shows delivered but was never received; agent collects claim details and processes a label refund |
| [`delivery_failure_followup`](delivery_failure_followup/) | Outbound | Calls customers whose package shows a delivery failure or return-to-sender status, collects a corrected address, and offers reshipping or a refund |
| [`shipping_rate_inquiry`](shipping_rate_inquiry/) | Inbound | Customer calls to get a rate quote; agent collects addresses and package dimensions and reads back the cheapest and fastest carrier options |

## Authentication

EasyPost uses HTTP Basic authentication with your API key as the username and an empty password:

```python
import requests
resp = requests.get(url, auth=(EASYPOST_API_KEY, ""), timeout=10)
```

Use test API keys (from the EasyPost dashboard Test mode) for development.

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `EASYPOST_API_KEY` | EasyPost API key (test or production) |
