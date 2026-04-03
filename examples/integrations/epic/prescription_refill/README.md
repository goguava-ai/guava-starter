# Prescription Refill — Epic Integration

An outbound voice agent that calls patients when a prescription refill is available. It confirms whether they want the refill, collects their preferred pharmacy, then submits a `MedicationRequest` to Epic — all in a single call.

## How It Works

**1. Reach the patient**

`reach_person()` ensures the refill confirmation only starts when the patient is on the line. If unreachable, a voicemail is left letting the patient know a refill is available and asking them to call back.

**2. Collect refill intent and preferences**

The agent identifies the medication and collects three fields:
- `confirm_refill` — "yes" or "no"
- `preferred_pharmacy` — name and location of their pharmacy (only asked if they said yes)
- `questions_for_pharmacist` — any questions to pass along to the pharmacist or prescriber (optional)

**3. After the call — conditionally submit to Epic**

`save_results()` only submits to Epic if the patient confirmed the refill. A `MedicationRequest` is posted with:
- `status: "active"` and `intent: "order"`
- `medicationCodeableConcept.text` set to the medication name
- A `note` field summarizing the pharmacy preference and any patient questions

If the patient declined, no Epic write is made.

**4. Outcome-based close**

- Confirmed refill → agent informs the patient the prescription has been submitted and will be ready within 24 hours.
- Declined → agent acknowledges and invites them to call back when ready.

## Epic FHIR Calls

| Timing | Method | Resource | Purpose |
|---|---|---|---|
| Post-call (conditional) | `POST` | `MedicationRequest` | Submit refill order when patient confirms |

## Setup

```bash
export GUAVA_AGENT_NUMBER="+1..."
export EPIC_BASE_URL="https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4"
export EPIC_ACCESS_TOKEN="..."
```

## Run

```bash
python -m examples.integrations.epic.prescription_refill \
  "+15551234567" \
  --name "Jane Doe" \
  --patient-id "pat456" \
  --medication "Metformin 500mg"
```

## Sample Output

```json
{
  "use_case": "prescription_refill",
  "patient_name": "Jane Doe",
  "medication": "Metformin 500mg",
  "fields": {
    "confirm_refill": "yes",
    "preferred_pharmacy": "CVS on Main Street",
    "questions_for_pharmacist": "Can I take this with my new blood pressure medication?"
  }
}
```
