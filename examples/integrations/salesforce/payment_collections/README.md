# Payment Collections

**Direction:** Outbound

Call customers with an outstanding balance to collect payment or arrange a resolution. The call outcome is logged as a Task on the Account and a custom `Collections_Status__c` field is updated.

## What it does

1. Fetches Account details pre-call via `GET /sobjects/Account/{id}`
2. Conducts a professional, empathetic collections conversation
3. Logs the call outcome as a completed Task via `POST /sobjects/Task`
4. Updates `Collections_Status__c` on the Account via `PATCH /sobjects/Account/{id}`

## Outcome Status Mapping

| Outcome | Collections Status |
|---|---|
| Paying now | Payment Received |
| Payment plan requested | Payment Plan |
| Promised to pay later | Promise to Pay |
| Disputes the amount | In Dispute |
| Refused to pay | Escalated |

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `SALESFORCE_INSTANCE_URL` | Your Salesforce org URL |
| `SALESFORCE_ACCESS_TOKEN` | OAuth2 Bearer token |

## Usage

```bash
python __main__.py +15551234567 --account-id 001... --name "Jane Smith" --amount '$4,200.00'
```

> **Note:** This example writes to `Collections_Status__c` on the Account object. Create it as a Picklist field with values: Payment Received, Payment Plan, Promise to Pay, In Dispute, Escalated.
