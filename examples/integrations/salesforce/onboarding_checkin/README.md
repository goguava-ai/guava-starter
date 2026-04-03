# Onboarding Check-In

**Direction:** Outbound

Call new customers to check in on their onboarding progress. The agent captures their setup status, surfaces blockers, and identifies what support they need. Results update `Onboarding_Status__c` and `Onboarding_Notes__c` on the Account, and a follow-up Task is created if action is needed.

## What it does

1. Fetches Account details pre-call via `GET /sobjects/Account/{id}`
2. Conducts a structured onboarding check-in conversation
3. Updates `Onboarding_Status__c` and `Onboarding_Notes__c` via `PATCH /sobjects/Account/{id}`
4. Logs the completed call as a Task via `POST /sobjects/Task`
5. Creates a future follow-up Task via `POST /sobjects/Task` if blockers or support needs were identified

## Onboarding Status Mapping

| Progress | Salesforce Status |
|---|---|
| Not started yet | Not Started |
| Just getting started / Partially complete | In Progress |
| Mostly done | Nearly Complete |
| Fully set up | Complete |

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

> **Note:** This example writes to custom fields `Onboarding_Status__c` (Picklist: Not Started, In Progress, Nearly Complete, Complete) and `Onboarding_Notes__c` (Long Text Area) on the Account object.
