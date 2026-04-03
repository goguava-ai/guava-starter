# Usage Alert — Snowflake Integration

An outbound voice agent that proactively calls a customer when their Meridian Analytics account is approaching its monthly data quota. The agent reads back their current usage figures, collects their decision on how to respond (upgrade plan or reduce usage), and writes the result back to Snowflake.

## How It Works

**1. Pre-call data fetch**

Before dialing, the agent queries the `ACCOUNT_ALERTS` table to retrieve the account's current usage in GB, quota limit, and usage percentage. This allows the agent to reference accurate figures the moment the call connects.

**2. Reach the customer**

The agent attempts to reach the named contact. If unavailable, it leaves a brief voicemail and ends.

**3. Deliver the usage alert**

The agent reads back the exact usage percentage and GB figures so the customer has concrete information to act on.

**4. Collect the decision**

The customer is asked whether they want to upgrade their plan or manage usage within the current quota. Any additional notes or questions are captured as a free-text field.

**5. Write back to Snowflake**

The customer's decision and notes are inserted into the `ALERT_RESPONSES` table via a parameterized `INSERT` statement, creating a timestamped record of the interaction.

**6. Close the call**

The agent provides next-step guidance appropriate to the customer's choice before ending the call.

## Snowflake API Calls

| Timing | Endpoint | Purpose |
|---|---|---|
| Pre-call | `POST /api/v2/statements` | Query `ACCOUNT_ALERTS` to fetch usage figures for the account |
| Post-collection | `POST /api/v2/statements` | Insert the customer's decision into `ALERT_RESPONSES` |

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
python -m examples.integrations.snowflake.usage_alert +15551234567 --account-id ACC-9921 --name "Jane Smith"
```

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `SNOWFLAKE_ACCOUNT` | Snowflake account identifier (e.g. `xy12345.us-east-1`) |
| `SNOWFLAKE_JWT_TOKEN` | Signed JWT for key-pair authentication |
| `SNOWFLAKE_WAREHOUSE` | Virtual warehouse to run queries against |
| `SNOWFLAKE_DATABASE` | Database containing the `ACCOUNT_ALERTS` and `ALERT_RESPONSES` tables |
| `SNOWFLAKE_SCHEMA` | Schema containing those tables |
| `SNOWFLAKE_ROLE` | Snowflake role to assume for the session |
