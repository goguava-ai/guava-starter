# Customer Data Lookup — Snowflake Integration

An inbound voice agent that answers customer calls, collects their email address, and retrieves their account details — plan, monthly usage, join date, and account status — directly from a Snowflake `CUSTOMERS` table.

## How It Works

**1. Greet and collect email**

The agent introduces itself as Alex from Meridian Analytics and asks the caller for the email address associated with their account.

**2. Query Snowflake**

A parameterized `SELECT` statement is issued against the `CUSTOMERS` table using the Snowflake SQL API. The email is passed as a bound parameter (`?` binding) to prevent injection and ensure correct type handling.

**3. Parse the result**

Column names are extracted from `resultSetMetaData.rowType` and zipped with the data rows to produce a structured record. If no matching row is found, the caller is informed and directed to support.

**4. Read back account details**

The agent reads back the customer's current plan, monthly usage in GB, join date, and account status in a natural, conversational way.

**5. Close the call**

The agent asks if there is anything else it can help with, then thanks the caller and ends the call.

## Snowflake API Calls

| Timing | Endpoint | Purpose |
|---|---|---|
| Post-collection | `POST /api/v2/statements` | Query the `CUSTOMERS` table by email to retrieve account details |

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
python -m examples.integrations.snowflake.customer_data_lookup
```

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `SNOWFLAKE_ACCOUNT` | Snowflake account identifier (e.g. `xy12345.us-east-1`) |
| `SNOWFLAKE_JWT_TOKEN` | Signed JWT for key-pair authentication |
| `SNOWFLAKE_WAREHOUSE` | Virtual warehouse to run queries against |
| `SNOWFLAKE_DATABASE` | Database containing the `CUSTOMERS` table |
| `SNOWFLAKE_SCHEMA` | Schema containing the `CUSTOMERS` table |
| `SNOWFLAKE_ROLE` | Snowflake role to assume for the session |
