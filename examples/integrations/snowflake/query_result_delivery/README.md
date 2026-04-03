# Query Result Delivery — Snowflake Integration

An outbound voice agent that proactively calls a data analyst when a long-running Snowflake query completes. The agent reads a plain-language summary of the results, confirms the analyst received the information, and captures any follow-up requests.

## How It Works

**1. Pre-call data fetch**

Before dialing, the agent queries the `SCHEDULED_QUERY_RESULTS` table to retrieve the query name, row count, status, completion time, and a human-readable summary. This information is loaded into the controller so it is available the moment the call connects.

**2. Reach the analyst**

The agent attempts to reach the named analyst. If unavailable, it leaves a brief voicemail noting the query has completed and directs them to their dashboard.

**3. Deliver the results**

The agent reads back the query name, completion time, status, row count, and — if present — a plain-language summary from the `SUMMARY_TEXT` column. If no summary is available, the analyst is directed to the dashboard for the full result set.

**4. Confirm receipt and capture follow-up**

The agent confirms the analyst heard the information and asks whether they need a follow-up from the data engineering team. Any follow-up details are captured as free text.

**5. Close the call**

The agent provides dashboard instructions and thanks the analyst, or notes the follow-up request before ending the call.

## Snowflake API Calls

| Timing | Endpoint | Purpose |
|---|---|---|
| Pre-call | `POST /api/v2/statements` | Query `SCHEDULED_QUERY_RESULTS` by query ID to retrieve result metadata and summary |

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
python -m examples.integrations.snowflake.query_result_delivery +15551234567 --query-id QRY-00482 --name "Dana Reyes"
```

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `SNOWFLAKE_ACCOUNT` | Snowflake account identifier (e.g. `xy12345.us-east-1`) |
| `SNOWFLAKE_JWT_TOKEN` | Signed JWT for key-pair authentication |
| `SNOWFLAKE_WAREHOUSE` | Virtual warehouse to run queries against |
| `SNOWFLAKE_DATABASE` | Database containing the `SCHEDULED_QUERY_RESULTS` table |
| `SNOWFLAKE_SCHEMA` | Schema containing the `SCHEDULED_QUERY_RESULTS` table |
| `SNOWFLAKE_ROLE` | Snowflake role to assume for the session |
