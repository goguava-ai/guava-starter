# Snowflake Integration

Voice agents that integrate with the [Snowflake SQL API](https://docs.snowflake.com/en/developer-guide/sql-api/index) to look up customer records, deliver usage health summaries, alert accounts approaching quota, and notify analysts when long-running queries complete — all without manual intervention.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`customer_data_lookup`](customer_data_lookup/) | Inbound | Customer calls to retrieve their account details — plan, usage, join date, and status — from Snowflake |
| [`account_health_check`](account_health_check/) | Inbound | Customer calls to hear a health summary of their account including quota utilization, overage events, and last activity |
| [`usage_alert`](usage_alert/) | Outbound | Proactively calls a customer when their data usage is approaching quota; collects their decision and writes it back to Snowflake |
| [`query_result_delivery`](query_result_delivery/) | Outbound | Calls a data analyst to deliver a plain-language summary of a completed long-running Snowflake query |

## Authentication

All examples use Snowflake key-pair JWT authentication:

```
Authorization: Bearer <jwt_token>
X-Snowflake-Authorization-Token-Type: KEYPAIR_JWT
```

Generate a key-pair, assign the public key to your Snowflake user, and sign a short-lived JWT to use as the bearer token. See the [Snowflake key-pair authentication guide](https://docs.snowflake.com/en/developer-guide/sql-api/authenticating) for full instructions.

## Common Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `SNOWFLAKE_ACCOUNT` | Snowflake account identifier (e.g. `xy12345.us-east-1`) |
| `SNOWFLAKE_JWT_TOKEN` | Signed JWT for key-pair authentication |
| `SNOWFLAKE_WAREHOUSE` | Virtual warehouse to run queries against |
| `SNOWFLAKE_DATABASE` | Target database |
| `SNOWFLAKE_SCHEMA` | Target schema |
| `SNOWFLAKE_ROLE` | Snowflake role to assume for the session |

## Snowflake API Reference

- [SQL API Overview](https://docs.snowflake.com/en/developer-guide/sql-api/index)
- [Submitting Statements](https://docs.snowflake.com/en/developer-guide/sql-api/submitting-requests)
- [Authenticating with Key-Pair JWT](https://docs.snowflake.com/en/developer-guide/sql-api/authenticating)
- [Handling Responses](https://docs.snowflake.com/en/developer-guide/sql-api/handling-responses)
