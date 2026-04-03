# Win/Loss Survey

**Direction:** Outbound

Call contacts on recently closed Opportunities to gather win/loss feedback. The survey captures the primary decision factor, competitive intelligence, and areas for improvement. Results are saved as a Note on the Opportunity and `Loss_Reason__c` is updated on losses.

## What it does

1. Fetches Opportunity details pre-call via `GET /sobjects/Opportunity/{id}`
2. Conducts a 5-question win/loss survey tailored to whether the deal was won or lost
3. Logs survey results as a Note via `POST /sobjects/Note`
4. Updates `Loss_Reason__c` on the Opportunity via `PATCH /sobjects/Opportunity/{id}` (lost deals only)
5. Logs a completed Task via `POST /sobjects/Task`

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `SALESFORCE_INSTANCE_URL` | Your Salesforce org URL |
| `SALESFORCE_ACCESS_TOKEN` | OAuth2 Bearer token |

## Usage

```bash
# Won deal
python __main__.py +15551234567 --opportunity-id 006... --name "Jane Smith" --outcome won

# Lost deal
python __main__.py +15551234567 --opportunity-id 006... --name "Jane Smith" --outcome lost
```

> **Note:** This example writes to `Loss_Reason__c` on the Opportunity object. Create it as a Text field (255) or Picklist under **Setup → Object Manager → Opportunity → Fields & Relationships**.
