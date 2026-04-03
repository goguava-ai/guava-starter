# Medication Reconciliation

**Direction:** Outbound

An outbound voice agent that calls patients ahead of hospital admission to reconcile their current medications against the active `MedicationRequest` list in Meditech Expanse, flags any discrepancies, and saves a reconciliation note as a FHIR `DocumentReference`.

## What it does

1. Pre-fetches all active `MedicationRequest` resources for the patient from Meditech Expanse before the call begins.
2. Places an outbound call and attempts to reach the patient by name using `reach_person`.
3. If connected and medications are on file: reads the list of active medications back to the patient and asks which ones they are still taking.
4. Collects any medications the patient has stopped, any medications they are taking that are not on file, and any new allergies or adverse reactions.
5. If no medications are on file: asks the patient whether they are currently taking any medications or supplements and captures their response.
6. Identifies discrepancies — stopped medications, unlisted medications, or new allergy reports.
7. Saves the full reconciliation summary as a FHIR `DocumentReference` (LOINC 56445-0, Medication summary) in Meditech Expanse, with a discrepancy flag in the description.
8. If discrepancies are found: informs the patient that the clinical team will review before admission and reminds them to bring all medication bottles.
9. If the patient does not answer: leaves a brief voicemail asking them to call back.

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Phone number the outbound call is placed from (E.164 format) |
| `MEDITECH_FHIR_BASE_URL` | Meditech Expanse FHIR R4 base URL (e.g. `https://fhir.meditech.com/r4`) |
| `MEDITECH_ACCESS_TOKEN` | OAuth 2.0 bearer token for the Meditech Expanse FHIR API |

## Usage

```bash
export GUAVA_AGENT_NUMBER="+1..."
export MEDITECH_FHIR_BASE_URL="https://fhir.meditech.com/r4"
export MEDITECH_ACCESS_TOKEN="..."

python __main__.py +15551234567 --name "Robert Chen" --patient-id PT-00789
```

Use `--help` to see all arguments without placing a call:

```bash
python __main__.py --help
```

## Meditech FHIR Calls

| Timing | Method | Resource | Purpose |
|---|---|---|---|
| Pre-call (in `__init__`) | `GET` | `MedicationRequest` | Fetch active medication list to present during the call |
| Post-call | `POST` | `DocumentReference` | Save reconciliation summary note with discrepancy flag |
