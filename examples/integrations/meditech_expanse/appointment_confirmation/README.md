# Appointment Confirmation

**Direction:** Outbound

An outbound voice agent that calls patients ahead of their scheduled hospital appointments to confirm attendance or capture cancellations with a reason.

## What it does

1. Pre-fetches the FHIR `Appointment` resource from Meditech Expanse to personalize the greeting with the correct service type and date/time.
2. Places an outbound call and attempts to reach the patient by name using `reach_person`.
3. Asks the patient whether they are confirming or cancelling their appointment.
4. If confirming: PATCHes the `Appointment` status to `booked` in Meditech and closes with pre-visit reminders.
5. If cancelling: collects the cancellation reason, then PATCHes the `Appointment` status to `cancelled` with the `cancelationReason` field populated.
6. If the patient does not answer: leaves a brief voicemail asking them to call back to confirm or reschedule.

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

python __main__.py +15551234567 \
  --name "Maria Gonzalez" \
  --patient-id PT-00456 \
  --appointment-id APT-00789
```

Use `--help` to see all arguments without placing a call:

```bash
python __main__.py --help
```

## Meditech FHIR Calls

| Timing | Method | Resource | Purpose |
|---|---|---|---|
| Pre-call (in `__init__`) | `GET` | `Appointment/{id}` | Fetch appointment details to personalize the greeting |
| If confirmed | `PATCH` | `Appointment/{id}` | Set status to `booked` |
| If cancelled | `PATCH` | `Appointment/{id}` | Set status to `cancelled` with cancellation reason |
