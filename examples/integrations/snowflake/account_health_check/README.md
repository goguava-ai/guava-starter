# Account Health Check — Snowflake Integration

An inbound voice agent that answers customer calls, looks up their account metrics in a Snowflake `ACCOUNT_METRICS` table, and delivers a plain-language health summary covering usage, quota status, overage events, and last activity.

## How It Works

**1. Greet and collect email**

The agent introduces itself as Sam from Meridian Analytics and asks the caller for the email address associated with their account.

**2. Query Snowflake**

A parameterized `SELECT` is run against `ACCOUNT_METRICS` using the Snowflake SQL API. The email is passed as a bound parameter to ensure safe, type-correct querying.

**3. Parse and assess health**

Column names from `resultSetMetaData.rowType` are zipped with the returned data row. Usage percentage is computed from `CURRENT_MONTH_USAGE_GB` and `QUOTA_GB`. A health label (healthy / moderate / critical) is assigned based on utilization thresholds.

**4. Deliver the summary**

The agent reads back the usage percentage, raw GB figures, overage event count, and last query date in a conversational summary. Accounts above 70% receive a recommendation to review their workloads.

**5. Close the call**

The agent checks if the caller has any other questions before thanking them and ending the call.

## Snowflake API Calls

| Timing | Endpoint | Purpose |
|---|---|---|
| Post-collection | `POST /api/v2/statements` | Query `ACCOUNT_METRICS` by email to retrieve usage and quota data |

## Setup

### 1. Get a Snowflake JWT token

Generate a key-pair for your Snowflake user, assign the public key, and sign a JWT. See the [Snowflake key-pair authentication guide](https://docs.snowflake.com/en/developer-guide/sql-api/authenticating).

### 2. Install dependencies

```bash
pip install guava requests
```

### 3. Set environment variables

```bash
export GUAVA_AGENT_NUMBER="+1..."
export SNOWFLAKE_ACCOUNT="xy12345.us-east-1"
export SNOWFLAKE_JWT_TOKEN="<your_jwt_token>"
export SNOWFLAKE_WAREHOUSE="COMPUTE_WH"
export SNOWFLAKE_DATABASE="ANALYTICS"
export SNOWFLAKE_SCHEMA="PUBLIC"
export SNOWFLAKE_ROLE="ANALYST"
```

### 4. Run

```bash
python -m examples.integrations.snowflake.account_health_check
```

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `SNOWFLAKE_ACCOUNT` | Snowflake account identifier (e.g. `xy12345.us-east-1`) |
| `SNOWFLAKE_JWT_TOKEN` | Signed JWT for key-pair authentication |
| `SNOWFLAKE_WAREHOUSE` | Virtual warehouse to run queries against |
| `SNOWFLAKE_DATABASE` | Database containing the `ACCOUNT_METRICS` table |
| `SNOWFLAKE_SCHEMA` | Schema containing the `ACCOUNT_METRICS` table |
| `SNOWFLAKE_ROLE` | Snowflake role to assume for the session |
