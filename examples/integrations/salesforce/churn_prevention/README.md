# Churn Prevention

**Direction:** Outbound

Proactively call at-risk customers to understand their concerns, gauge renewal likelihood, and capture a next action. Results are logged as a Task on the Account and the `Churn_Risk__c` custom field is updated.

## What it does

1. Fetches Account details pre-call via `GET /sobjects/Account/{id}`
2. Reaches the contact and conducts a satisfaction and retention check-in
3. Logs the call outcome as a completed Task via `POST /sobjects/Task`
4. Updates `Churn_Risk__c` on the Account via `PATCH /sobjects/Account/{id}`

## Churn Risk Mapping

| Satisfaction | Risk Level |
|---|---|
| Very dissatisfied / Dissatisfied | High |
| Neutral | Medium |
| Satisfied / Very satisfied | Low |

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `SALESFORCE_INSTANCE_URL` | Your Salesforce org URL |
| `SALESFORCE_ACCESS_TOKEN` | OAuth2 Bearer token |

## Usage

```bash
python __main__.py +15551234567 --account-id 001... --name "Jane Smith"
```

> **Note:** This example writes to a custom field `Churn_Risk__c` on the Account object. Create it in your org under **Setup → Object Manager → Account → Fields & Relationships** as a Picklist with values: High, Medium, Low.
