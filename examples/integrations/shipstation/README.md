# ShipStation Integration

Voice agents that integrate with the [ShipStation API](https://www.shipstation.com/docs/api/) to handle order tracking, delivery exception management, return authorization, and proactive shipping delay notifications.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`order_tracking`](order_tracking/) | Inbound | Customer calls to look up their order status and get carrier/tracking details |
| [`delivery_exception`](delivery_exception/) | Outbound | Call customers whose shipment has a delivery exception to collect updated delivery instructions |
| [`return_authorization`](return_authorization/) | Inbound | Customer calls to initiate a return — agent verifies eligibility and issues a prepaid return label |
| [`shipping_delay_notification`](shipping_delay_notification/) | Outbound | Proactively call customers about delayed orders and offer to wait, cancel, or expedite |

## Authentication

ShipStation uses HTTP Basic authentication with a base64-encoded `API_KEY:API_SECRET` pair.

```python
import base64
credentials = base64.b64encode(f"{API_KEY}:{API_SECRET}".encode()).decode()
headers = {"Authorization": f"Basic {credentials}"}
```

Get API credentials in ShipStation: **Account** → **API Settings**.

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `SHIPSTATION_API_KEY` | ShipStation API key |
| `SHIPSTATION_API_SECRET` | ShipStation API secret |
