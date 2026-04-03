# AfterShip Integration

Voice agents that integrate with the [AfterShip Tracking API](https://www.aftership.com/docs/aftership/quickstart) to handle inbound shipment inquiries and proactively reach customers about delivery events — without requiring them to check tracking websites or navigate IVR menus.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`shipment_status_check`](shipment_status_check/) | Inbound | Customer calls to check the status of a shipment by tracking number |
| [`delivery_exception_notification`](delivery_exception_notification/) | Outbound | Agent calls customer when a delivery exception or failed attempt is detected |
| [`return_label_request`](return_label_request/) | Inbound | Customer calls to initiate a return; a new return tracking is created in AfterShip |
| [`proactive_delivery_update`](proactive_delivery_update/) | Outbound | Agent calls customer when their package is out for delivery |

## Authentication

All examples authenticate using the AfterShip API key header:

```
as-api-key: YOUR_API_KEY
```

Get your API key in the AfterShip dashboard: **Settings** → **API** → **Generate API Key**.

## Common Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `AFTERSHIP_API_KEY` | AfterShip API key |

## AfterShip API Reference

- [Trackings](https://www.aftership.com/docs/aftership/quickstart/api-quick-start)
- [Tracking Status Tags](https://www.aftership.com/docs/aftership/quickstart/tracking-status)
- [Couriers/Slugs](https://www.aftership.com/docs/aftership/quickstart/supported-couriers)
