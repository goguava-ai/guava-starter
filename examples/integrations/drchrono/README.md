# DrChrono EHR Integration

Voice agents that integrate with the [DrChrono REST API](https://app.drchrono.com/api-docs) to handle appointment scheduling, appointment reminders, new patient intake, prescription refill requests, and lab results notifications — without routing patients to a portal or live agent.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`appointment_scheduling`](appointment_scheduling/) | Inbound | Patient calls to schedule a new appointment end-to-end |
| [`appointment_reminder`](appointment_reminder/) | Outbound | Remind patients of upcoming appointments and confirm attendance |
| [`patient_intake`](patient_intake/) | Inbound | Collect new patient demographics and create a patient record |
| [`prescription_refill`](prescription_refill/) | Inbound | Accept refill requests and route them to the care team |
| [`lab_results_notification`](lab_results_notification/) | Outbound | Notify patients that lab results are available |

## Authentication

DrChrono uses OAuth2 Bearer tokens. Obtain an access token from the DrChrono developer settings:

1. Log in to DrChrono and navigate to **Account** > **API** > **Developer Settings**
2. Create an OAuth2 application and note your client ID and client secret
3. Exchange credentials for a Bearer token via the OAuth2 authorization flow
4. Export the token as `DRCHRONO_ACCESS_TOKEN`

All requests include the token as an HTTP header:

```python
HEADERS = {"Authorization": f"Bearer {DRCHRONO_ACCESS_TOKEN}", "Content-Type": "application/json"}
```

Tokens expire; consult the [DrChrono API docs](https://app.drchrono.com/api-docs) for refresh token handling in production deployments.

## Common Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `DRCHRONO_ACCESS_TOKEN` | DrChrono OAuth2 Bearer token |
| `DRCHRONO_DOCTOR_ID` | Integer ID of the doctor to assign records and calls to |
| `DRCHRONO_OFFICE_ID` | Integer ID of the practice office |

## DrChrono API Reference

- **Base URL:** `https://app.drchrono.com/api`
- [Patients](https://app.drchrono.com/api-docs/#patients) — `GET /patients`, `POST /patients`, `PATCH /patients/{id}`
- [Appointments](https://app.drchrono.com/api-docs/#appointments) — `GET /appointments`, `POST /appointments`, `PATCH /appointments/{id}`
- [Clinical Notes](https://app.drchrono.com/api-docs/#clinical_notes) — `GET /clinical_notes`
- [Lab Documents](https://app.drchrono.com/api-docs/#lab_documents) — `GET /lab_documents`, `PATCH /lab_documents/{id}`
- [Call Logs](https://app.drchrono.com/api-docs/#call_logs) — `POST /call_logs`

## HIPAA Compliance Considerations

These examples interact with Protected Health Information (PHI). Before deploying in a production environment:

- **Data in transit:** All API calls are made over HTTPS. Never transmit PHI over unencrypted channels.
- **Access control:** Restrict `DRCHRONO_ACCESS_TOKEN` and all env vars to authorized systems only. Rotate tokens regularly and use a secrets manager rather than plain environment variables in production.
- **Minimum necessary:** Agents collect and transmit only the data required to complete each specific task. Do not log PHI to unprotected log files or consoles.
- **Voicemail and unanswered calls:** When a patient cannot be reached, agents leave only the practice name and a callback number — no clinical details, diagnosis information, or appointment specifics.
- **Outbound identity verification:** Outbound agents use `reach_person` to confirm they are speaking with the correct individual before discussing any health-related information.
- **Lab results:** The lab results notification agent never reads out actual lab values or clinical findings over the phone. It only notifies the patient that results are available and directs them to a secure channel.
- **Business Associate Agreement:** Ensure you have a signed BAA with Guava and with any other vendors in the call path before handling PHI.
- **Audit logging:** DrChrono call logs (`POST /call_logs`) are used to document each outbound call for auditing purposes.
