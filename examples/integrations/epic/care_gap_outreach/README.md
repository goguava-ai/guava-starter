# Care Gap Outreach — Epic Integration

An outbound voice agent that calls patients who are overdue for a preventive care service — annual wellness visit, colorectal cancer screening, mammogram, etc. — and encourages them to schedule it. The patient's response is logged in Epic as a `CommunicationRequest`.

## How It Works

**1. Reach the patient**

`reach_person()` handles the outreach and voicemail. If unreachable, a friendly voicemail explains the call is about an overdue care service and asks them to call back.

**2. Explain the care gap and collect intent**

The agent introduces the specific care gap (passed in as `--care-gap`) and collects:
- `interested_in_scheduling` — "yes", "no", or "already scheduled"
- `preferred_timeframe` — when they'd like to come in (only if they said yes)
- `questions` — any questions about why the service is recommended (optional)

**3. After the call — post a CommunicationRequest to Epic**

`save_results()` posts a `CommunicationRequest` (status `completed`) to Epic summarizing the outreach outcome: whether the patient is interested, their preferred timeframe, and any questions raised. This closes the loop on the care gap workflow in Epic and gives the scheduling team the information they need to follow up.

**4. Three-way outcome close**

The agent's closing message handles all three outcomes:
- Wants to schedule → scheduling coordinator will call back within one business day.
- Already scheduled → acknowledges and celebrates the good news.
- Declined → respects the decision, provides the clinic number for when they're ready.

## Epic FHIR Calls

| Timing | Method | Resource | Purpose |
|---|---|---|---|
| Post-call | `POST` | `CommunicationRequest` | Log outreach outcome and patient scheduling intent |

## Setup

```bash
export GUAVA_AGENT_NUMBER="+1..."
export EPIC_BASE_URL="https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4"
export EPIC_ACCESS_TOKEN="..."
```

## Run

```bash
python -m examples.integrations.epic.care_gap_outreach \
  "+15551234567" \
  --name "Jane Doe" \
  --patient-id "pat456" \
  --care-gap "annual wellness visit"
```

The `--care-gap` value is spoken verbatim by the agent, so make it patient-friendly (e.g. "colorectal cancer screening" rather than "colonoscopy HEDIS measure").

## Sample Output

```json
{
  "use_case": "care_gap_outreach",
  "care_gap": "annual wellness visit",
  "fields": {
    "interested_in_scheduling": "yes",
    "preferred_timeframe": "within the next two weeks",
    "questions": null
  }
}
```
