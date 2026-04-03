# Salesforce CRM Integration

Voice agents that integrate with the [Salesforce REST API](https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/) to capture leads, manage cases, run surveys, update records, and automate the full customer lifecycle — without manual CRM entry.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`contact_update`](contact_update/) | Inbound | Customer calls to update their phone, title, address, or email in Salesforce |
| [`account_inquiry`](account_inquiry/) | Inbound | Look up an Account's status, open Cases, and active Opportunities from a voice call |
| [`service_scheduling`](service_scheduling/) | Inbound | Customer schedules an on-site appointment; creates a Salesforce Event and Case |
| [`product_feedback`](product_feedback/) | Inbound | Customer shares product feedback or a feature request; creates a Case and Chatter post |
| [`churn_prevention`](churn_prevention/) | Outbound | Proactively call at-risk customers to capture concerns and update churn risk |
| [`contract_renewal`](contract_renewal/) | Outbound | Call customers nearing contract expiration; capture intent and advance Opportunity stage |
| [`nps_survey`](nps_survey/) | Outbound | Collect Net Promoter Score from customers; save to a custom `NPS_Response__c` object |
| [`payment_collections`](payment_collections/) | Outbound | Call customers with an outstanding balance; log outcome and update collections status |
| [`win_loss_survey`](win_loss_survey/) | Outbound | Post-deal survey for won or lost Opportunities; save feedback as a Note and update `Loss_Reason__c` |
| [`onboarding_checkin`](onboarding_checkin/) | Outbound | Check in with new customers on onboarding progress; update status and create follow-up Tasks |

## Authentication

All examples use OAuth 2.0 Bearer token authentication:

```
Authorization: Bearer {SALESFORCE_ACCESS_TOKEN}
```

Obtain a token via the [Salesforce OAuth 2.0 flow](https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/quickstart_oauth.htm) (Username-Password, JWT Bearer, or Connected App). For server-to-server use, the **JWT Bearer Flow** is recommended.

## Common Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `SALESFORCE_INSTANCE_URL` | Your Salesforce org URL (e.g. `https://yourorg.my.salesforce.com`) |
| `SALESFORCE_ACCESS_TOKEN` | OAuth2 Bearer token for the Salesforce REST API |

## Salesforce API Reference

- [REST API Developer Guide](https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/)
- [SOQL Reference](https://developer.salesforce.com/docs/atlas.en-us.soql_sosl.meta/soql_sosl/)
- [Standard Objects](https://developer.salesforce.com/docs/atlas.en-us.object_reference.meta/object_reference/sforce_api_objects_list.htm)
- [Composite Resources](https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/resources_composite.htm)

## Custom Fields

Several examples write to custom fields. See the individual README files for setup instructions:

| Example | Custom Fields Required |
|---|---|
| `churn_prevention` | `Account.Churn_Risk__c` (Picklist) |
| `nps_survey` | Custom object `NPS_Response__c` |
| `payment_collections` | `Account.Collections_Status__c` (Picklist) |
| `win_loss_survey` | `Opportunity.Loss_Reason__c` (Text) |
| `onboarding_checkin` | `Account.Onboarding_Status__c` (Picklist), `Account.Onboarding_Notes__c` (Long Text Area) |
