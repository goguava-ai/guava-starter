# Insurance Update — Epic Integration

An outbound voice agent that calls patients before an upcoming visit to collect and verify their current insurance information, then writes it to Epic as a `Coverage` resource — ensuring billing has accurate coverage details before the patient walks in.

## How It Works

**1. Reach the patient**

`reach_person()` ensures the insurance collection only starts with a live patient on the line. If unreachable, a voicemail is left asking them to call back before their visit.

**2. Collect insurance details**

The agent walks through the key fields from the patient's insurance card:
- `insurance_provider` — insurer name (Blue Cross Blue Shield, Aetna, Medicare, etc.)
- `member_id` — member ID number from the card
- `group_number` — group number, or "none" for individual plans
- `subscriber_name` — primary policyholder (may differ from the patient)
- `insurance_confirmed` — the agent reads back all details and asks the patient to confirm accuracy

**3. After the call — create a Coverage resource in Epic**

`save_results()` posts a `Coverage` resource to Epic with:
- `status: "active"`
- `beneficiary` linked to the patient FHIR ID
- `payor` set to the insurer name
- Two `class` entries: one for `group` (group number) and one for `member` (member ID)
- `subscriber` set to the subscriber name

This gives the billing and front-desk teams a verified, structured coverage record in Epic.

**4. Close**

The agent thanks the patient, confirms their insurance is updated, and reminds them to bring their card to the appointment.

## Epic FHIR Calls

| Timing | Method | Resource | Purpose |
|---|---|---|---|
| Post-call | `POST` | `Coverage` | Create verified insurance coverage record linked to the patient |

## Setup

```bash
export GUAVA_AGENT_NUMBER="+1..."
export EPIC_BASE_URL="https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4"
export EPIC_ACCESS_TOKEN="..."
```

## Run

```bash
python -m examples.integrations.epic.insurance_update \
  "+15551234567" \
  --name "Jane Doe" \
  --patient-id "pat456"
```

## Sample Output

```json
{
  "use_case": "insurance_update",
  "patient_name": "Jane Doe",
  "patient_id": "pat456",
  "fields": {
    "insurance_provider": "Blue Cross Blue Shield",
    "member_id": "XYZ123456789",
    "group_number": "98765",
    "subscriber_name": "Jane Doe",
    "insurance_confirmed": "confirmed"
  }
}
```
