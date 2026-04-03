# Change Healthcare Integration

Voice agents that integrate with the [Change Healthcare (Optum) Medical Network API](https://developers.changehealthcare.com) to verify patient eligibility, check claim status, and coordinate prior authorizations — all during a phone call.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`eligibility_check`](eligibility_check/) | Inbound | Patient calls to verify insurance coverage; agent submits a real-time 270/271 eligibility inquiry |
| [`claim_status`](claim_status/) | Inbound | Patient or billing staff calls to check the status of a submitted claim via a 276/277 inquiry |
| [`prior_auth_status`](prior_auth_status/) | Inbound | Clinical or admin staff checks whether a prior authorization has been approved for a procedure |
| [`claim_submission_trigger`](claim_submission_trigger/) | Outbound | Agent calls a contact to confirm billing details and then submits an 837P professional claim |

## Authentication

All examples use Change Healthcare's OAuth 2.0 client credentials flow:

```
POST /apip/auth/v2/token
{"client_id": "...", "client_secret": "..."}
→ {"access_token": "..."}
```

The returned token is passed as `Authorization: Bearer {token}` on all subsequent requests.

## Common Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `CHANGE_HEALTHCARE_CLIENT_ID` | OAuth client ID from the Change Healthcare developer portal |
| `CHANGE_HEALTHCARE_CLIENT_SECRET` | OAuth client secret |
| `CHANGE_HEALTHCARE_BASE_URL` | API base URL (default: `https://apis.changehealthcare.com`) |
| `CHANGE_HEALTHCARE_TRADING_PARTNER_ID` | Payer trading partner service ID (e.g. `000050` for BCBS) |
| `PROVIDER_NPI` | Your organization's NPI number |
| `PROVIDER_TAX_ID` | Tax ID / EIN (required for claim submission) |

## Change Healthcare API Reference

- [Medical Eligibility (270/271)](https://developers.changehealthcare.com/eligibilityandclaimsstatus/reference/medicaleligibility)
- [Claim Status (276/277)](https://developers.changehealthcare.com/eligibilityandclaimsstatus/reference/claimstatus)
- [Professional Claims (837P)](https://developers.changehealthcare.com/eligibilityandclaimsstatus/reference/professionalclaims)
- [Prior Authorization (278)](https://developers.changehealthcare.com/eligibilityandclaimsstatus/reference/priorauthorization)
