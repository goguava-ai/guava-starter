# CCaaS Integration Examples

These examples show how Guava voice agents integrate with existing contact center (CCaaS) infrastructure — pushing call results, creating contacts, logging dispositions, and creating follow-up tasks via each platform's API.

## Common Pattern

Each example extends the standard Guava `CallController` pattern by adding a CCaaS API push in `save_results()`. All API calls are wrapped in `try/except` so the Guava call completes gracefully even if the CCaaS API is unreachable.

## Examples

| Platform | Pattern | Scenario | API Integration |
|---|---|---|---|
| **nice_cxone** | Inbound | Support triage | `POST /contacts` → `POST /contacts/{id}/custom-data` (Bearer) |
| **ringba** | Outbound | Lead qualification | `POST /v2/{accountId}/campaigns/{campaignId}/calls` (Bearer) |
| **ringcentral** | Inbound | Order status inquiry | `POST /restapi/v1.0/.../address-book/contact` (Bearer) |
| **five9** | Outbound | Satisfaction survey | `POST /orgs/{orgId}/contacts` (HTTP Basic) |
| **talkdesk** | Inbound | Billing inquiry | `POST /contacts` → `POST /interactions` (Bearer, two-step) |
| **amazon_connect** | Inbound | Tech support → task | `connect_client.start_task_contact()` via boto3 (IAM) |
| **webex_cc** | Outbound | Appointment confirmation | `POST /v1/contactCenter/tasks` (Bearer) |

## Usage

Inbound examples (nice_cxone, ringcentral, talkdesk, amazon_connect):

```bash
export GUAVA_AGENT_NUMBER="+1..."
# Set platform-specific env vars (see each __main__.py)
python -m examples.ccaas.nice_cxone
```

Outbound examples (ringba, five9, webex_cc):

```bash
export GUAVA_AGENT_NUMBER="+1..."
# Set platform-specific env vars (see each __main__.py)
python -m examples.ccaas.ringba "+15551234567" --name "Jane Doe"
python -m examples.ccaas.webex_cc "+15551234567" --name "John Smith" --appointment "March 15 at 2:00 PM"
```

## Environment Variables

Each example requires its own set of platform credentials. See the top of each `__main__.py` for the full list. All examples also require `GUAVA_AGENT_NUMBER`.

| Platform | Required Env Vars |
|---|---|
| nice_cxone | `CXONE_BASE_URL`, `CXONE_ACCESS_TOKEN`, `CXONE_SKILL_ID` |
| ringba | `RINGBA_API_URL`, `RINGBA_API_TOKEN`, `RINGBA_ACCOUNT_ID`, `RINGBA_CAMPAIGN_ID` |
| ringcentral | `RINGCENTRAL_SERVER_URL`, `RINGCENTRAL_ACCESS_TOKEN` |
| five9 | `FIVE9_API_URL`, `FIVE9_USERNAME`, `FIVE9_PASSWORD`, `FIVE9_CAMPAIGN_NAME` |
| talkdesk | `TALKDESK_BASE_URL`, `TALKDESK_API_KEY` |
| amazon_connect | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`, `CONNECT_INSTANCE_ID`, `CONNECT_CONTACT_FLOW_ID` |
| webex_cc | `WEBEX_CC_BASE_URL`, `WEBEX_CC_ACCESS_TOKEN`, `WEBEX_CC_ORG_ID` |
