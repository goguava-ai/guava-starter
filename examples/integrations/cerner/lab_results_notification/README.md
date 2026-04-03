# Lab Results Notification

**Direction:** Outbound

Call a patient to notify them that their lab results are available. The agent shares a plain-language summary of the results, answers questions about next steps, and logs a FHIR `Communication` resource to document the notification.

## What it does

1. Fetches `Observation` resources by ID pre-call via `GET /Observation/{id}`
2. Formats each result into a plain-language description (name, value, unit, interpretation)
3. Delivers the notification and captures acknowledgment and follow-up preferences
4. Creates a `Communication` resource via `POST /Communication` to document the call

## FHIR Resources Used

| Resource | Operation |
|---|---|
| `Observation` | Read (pre-call) |
| `Communication` | Create (post-call log) |

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `CERNER_FHIR_BASE_URL` | Cerner FHIR R4 base URL |
| `CERNER_ACCESS_TOKEN` | OAuth 2.0 Bearer token |

## Usage

```bash
python __main__.py +15551234567 \
  --patient-id "Patient/12345" \
  --name "Jane Smith" \
  --observation-ids "obs_001" "obs_002" \
  --provider "Johnson"
```
