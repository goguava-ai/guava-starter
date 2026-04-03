# Availity Integration

Voice agents that integrate with the [Availity API](https://developer.availity.com) to handle healthcare administrative workflows over the phone — including insurance eligibility verification, claim status inquiries, prior authorization checks, and benefits inquiries — reducing hold times and manual work for front-desk staff and patients.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`eligibility_verification`](eligibility_verification/) | Inbound | Verify a patient's insurance eligibility in real time during an inbound call |
| [`claim_status_inquiry`](claim_status_inquiry/) | Inbound | Patient or staff calls to check the status of a submitted claim |
| [`prior_authorization_check`](prior_authorization_check/) | Inbound | Check whether a prior authorization is on file for a procedure or service |
| [`benefits_inquiry`](benefits_inquiry/) | Inbound | Patient calls to ask about their coverage details — deductible, copay, out-of-pocket max |

## Authentication

All examples use OAuth2 client credentials to obtain a Bearer token:

```python
import requests

def get_access_token(client_id, client_secret):
    resp = requests.post(
        "https://api.availity.com/availity/v1/token",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        auth=(client_id, client_secret),
        data={"grant_type": "client_credentials", "scope": "hipaa"},
    )
    resp.raise_for_status()
    return resp.json()["access_token"]
```

Obtain credentials from the Availity developer portal: **Developer Settings** → **Applications** → **Create Application**.

## Common Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `AVAILITY_CLIENT_ID` | Availity application client ID |
| `AVAILITY_CLIENT_SECRET` | Availity application client secret |
| `AVAILITY_PROVIDER_ID` | Your organization's NPI or Availity provider ID |
| `AVAILITY_PAYER_ID` | Default payer ID (can be overridden per call) |

## Availity API Reference

- [Eligibility and Benefits](https://developer.availity.com/partner/documentation/eligibility)
- [Claim Status](https://developer.availity.com/partner/documentation/claim-status)
- [Prior Authorization](https://developer.availity.com/partner/documentation/authorizations)
- [API Authentication](https://developer.availity.com/partner/documentation/auth)
