# Care Gap Outreach

**Direction:** Outbound

Calls patients who are overdue for preventive care (e.g., annual wellness visit, mammogram, colorectal screening). Gauges scheduling intent and posts a CommunicationRequest to the eClinicalWorks chart to track the outreach outcome.

## What it does

1. Calls the patient and explains the care gap
2. Identifies any scheduling barriers
3. Captures scheduling intent (schedule now / follow up later / not interested)
4. Posts a `CommunicationRequest` via `POST /CommunicationRequest` with intent note

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `ECW_BASE_URL` | eClinicalWorks FHIR R4 base URL |
| `ECW_TOKEN_URL` | OAuth token endpoint |
| `ECW_CLIENT_ID` | SMART on FHIR client ID |
| `ECW_CLIENT_SECRET` | SMART on FHIR client secret |

## Usage

```bash
python -m examples.integrations.eclinicalworks.care_gap_outreach "+15551234567" --name "Jane Doe" --patient-id "pat-456" --care-gap "annual wellness visit"
```
