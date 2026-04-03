# Waystar Integration

Voice agents that integrate with the [Waystar RCM platform](https://www.waystar.com) to perform real-time eligibility checks, look up claim status, verify prior authorizations, and proactively notify patients of claim outcomes.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`eligibility_verification`](eligibility_verification/) | Inbound | Patient or front-desk staff calls to verify insurance eligibility in real time |
| [`claim_status_inquiry`](claim_status_inquiry/) | Inbound | Billing staff or patients call to check the status of a submitted claim |
| [`prior_auth_lookup`](prior_auth_lookup/) | Inbound | Clinical staff looks up prior authorization status for a scheduled procedure |
| [`denial_notification`](denial_notification/) | Outbound | Agent calls patient to notify them of a claim denial and gather their preferred next step |

## Authentication

All examples use OAuth 2.0 client credentials:

```
POST {WAYSTAR_BASE_URL}/auth/oauth2/token
grant_type=client_credentials&client_id={id}&client_secret={secret}
→ {"access_token": "..."}
```

## Common Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `WAYSTAR_CLIENT_ID` | OAuth client ID from the Waystar developer portal |
| `WAYSTAR_CLIENT_SECRET` | OAuth client secret |
| `WAYSTAR_BASE_URL` | Waystar API base URL (default: `https://api.waystar.com`) |
| `WAYSTAR_PAYER_ID` | Default payer ID for your primary payer |
| `PROVIDER_NPI` | Your organization's NPI number |

## Waystar API Reference

- [Eligibility API](https://www.waystar.com/solutions/eligibility-benefits/)
- [Claim Status API](https://www.waystar.com/solutions/claim-management/)
- [Prior Authorization API](https://www.waystar.com/solutions/prior-authorization/)
- [Claims Management](https://www.waystar.com/solutions/claim-management/)
