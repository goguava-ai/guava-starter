# Medication Inquiry

**Direction:** Inbound

An inbound voice agent that picks up when a patient calls Valley General Hospital to ask about the medications currently on file for them. The agent verifies the patient's identity, retrieves their active `MedicationStatement` resources from Meditech Expanse, reads the list back to the patient, and handles four possible follow-up needs: questions for the care team, a refill request, a simple verification check, or a report that a medication on file is incorrect.

## What it does

1. Answers inbound calls to the hospital's medication inquiry line.
2. Collects first name, last name, and date of birth to verify the patient's identity.
3. Looks up the patient in Meditech Expanse (`GET /Patient`) by last name and date of birth.
4. If no record is found: informs the caller and closes the call with guidance to contact patient services.
5. If a record is found: fetches all active `MedicationStatement` resources (`GET /MedicationStatement?status=active`) and extracts the medication name and dosage text from each.
6. Reads the active medication list back to the patient.
7. Asks what they would like to do: have questions, need refill, just checking, or wrong medication listed.
8. Closes the call with instructions appropriate to each outcome:
   - **Have questions**: pharmacy callback within one business day.
   - **Need refill**: refill request forwarded to prescribing provider, processed within 1–2 days.
   - **Wrong medication listed**: escalated to care team for record correction, provider will follow up.
   - **Just checking**: friendly confirmation and close.

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Phone number assigned to the Guava voice agent (E.164 format) |
| `MEDITECH_FHIR_BASE_URL` | Meditech Expanse FHIR R4 base URL (e.g. `https://fhir.meditech.com/r4`) |
| `MEDITECH_ACCESS_TOKEN` | OAuth 2.0 bearer token for the Meditech Expanse FHIR API |

## Usage

```bash
export GUAVA_AGENT_NUMBER="+1..."
export MEDITECH_FHIR_BASE_URL="https://fhir.meditech.com/r4"
export MEDITECH_ACCESS_TOKEN="..."

python __main__.py
```

The agent listens for inbound calls. Each call is handled by a new `MedicationInquiryController` instance.

## Meditech FHIR Calls

| Timing | Method | Resource | Purpose |
|---|---|---|---|
| Mid-call | `GET` | `Patient` | Look up patient FHIR ID by last name and date of birth |
| Mid-call | `GET` | `MedicationStatement` | Fetch all active medications on file for the patient |
