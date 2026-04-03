# NPS Survey

**Direction:** Outbound

Call customers to collect a Net Promoter Score survey. The score, category (Promoter / Passive / Detractor), and verbatim feedback are saved to a custom `NPS_Response__c` object in Salesforce, and a Task is logged on the Contact.

## What it does

1. Reaches the contact and conducts a 3-question NPS survey (score, reason, improvement suggestion)
2. Looks up the Salesforce Contact by email via SOQL `GET /query`
3. Creates an `NPS_Response__c` record via `POST /sobjects/NPS_Response__c`
4. Logs a completed Task via `POST /sobjects/Task`

## NPS Category Mapping

| Score | Category |
|---|---|
| 9–10 | Promoter |
| 7–8 | Passive |
| 0–6 | Detractor |

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `SALESFORCE_INSTANCE_URL` | Your Salesforce org URL |
| `SALESFORCE_ACCESS_TOKEN` | OAuth2 Bearer token |

## Usage

```bash
python __main__.py +15551234567 --name "Jane Smith" --email jane@example.com
```

> **Note:** This example writes to a custom object `NPS_Response__c`. Create it in your org under **Setup → Object Manager → Create → Custom Object** with fields: `Contact__c` (Lookup/Contact), `Account__c` (Lookup/Account), `NPS_Score__c` (Number), `NPS_Category__c` (Picklist: Promoter, Passive, Detractor), `Verbatim_Feedback__c` (Long Text Area), `Survey_Date__c` (Date), `Channel__c` (Text).
