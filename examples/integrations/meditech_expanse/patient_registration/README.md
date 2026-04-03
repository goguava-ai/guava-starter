# Patient Registration

**Direction:** Inbound

An inbound voice agent that answers when a patient calls St. Raphael Medical Center to provide or update their demographic and insurance information before a visit, then writes the complete record to Meditech Expanse via PUT (existing patients) or POST (new patients).

## What it does

1. Answers inbound calls to the hospital's pre-registration line.
2. Collects full name, date of birth, home address, phone, email, insurance provider, insurance member ID, group number, and emergency contact.
3. Searches Meditech Expanse (`GET /Patient`) by last name and date of birth to determine if a record already exists.
4. If an existing record is found: issues a `PUT /Patient/{id}` to fully replace the demographic record with all collected information.
5. If no record is found: issues a `POST /Patient` to create a new FHIR Patient resource with all demographics, address, insurance identifiers, and emergency contact.
6. Closes the call with a confirmation and next-steps message appropriate to whether the record was created or updated.

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

The agent listens for inbound calls. Each call is handled by a new `PatientRegistrationController` instance.

## Meditech FHIR Calls

| Timing | Method | Resource | Purpose |
|---|---|---|---|
| Post-collection | `GET` | `Patient` | Search for an existing patient record by last name and date of birth |
| If found | `PUT` | `Patient/{id}` | Replace the full demographic record with all newly collected fields |
| If not found | `POST` | `Patient` | Create a new patient record with complete demographics and insurance |
