# Denial Notification — Waystar Integration

An outbound voice agent that calls patients to notify them of an insurance claim denial. The agent explains the denial reason, presents the patient's options (appeal, self-contact, self-pay), and records the outcome back to the claim in Waystar.

## How It Works

**1. Initiate an outbound call with claim context**

Claim details are passed via CLI arguments. `reach_person()` ensures the agent is speaking with the patient before discussing sensitive billing information.

**2. Deliver the notification**

The agent explains the denial, the reason, and presents three options: file an appeal, contact insurance directly, or arrange self-pay.

**3. Record the outcome in Waystar**

`update_claim_followup_status()` sends a `PATCH /claims/v1/{id}` request to update the claim's workflow status to `patient_notified` and appends a note with the patient's chosen next step.

**4. Close appropriately**

The agent's closing message adapts to the patient's choice, setting the right expectations for each path.

## Waystar API Calls

| Timing | Method | Endpoint | Purpose |
|---|---|---|---|
| Pre-call | `POST` | `/auth/oauth2/token` | Obtain OAuth access token |
| Pre-call | `GET` | `/claims/v1/{id}` | Fetch claim detail (optional enrichment) |
| Post-call | `PATCH` | `/claims/v1/{id}` | Record notification outcome on the claim |

## Setup

```bash
export GUAVA_AGENT_NUMBER="+1..."
export WAYSTAR_CLIENT_ID="..."
export WAYSTAR_CLIENT_SECRET="..."
```

## Run

```bash
python -m examples.integrations.waystar.denial_notification \
  +15551234567 \
  --name "Jane Doe" \
  --claim-id "WS-2026031500123" \
  --denial-reason "Service not covered under current plan" \
  --service "MRI lumbar spine" \
  --service-date "2026-03-01" \
  --amount "850.00"
```

## Sample Output

```json
{
  "use_case": "denial_notification",
  "patient_name": "Jane Doe",
  "claim_id": "WS-2026031500123",
  "denial_reason": "Service not covered under current plan",
  "service_date": "2026-03-01",
  "claim_amount": "850.00",
  "preferred_next_step": "file an appeal on my behalf"
}
```
