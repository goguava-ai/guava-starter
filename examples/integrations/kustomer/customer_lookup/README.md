# Customer Lookup — Kustomer Integration

An inbound voice agent that allows callers to look up their Kustomer customer profile and hear a summary of their recent case history — by email or by phone number.

## How It Works

**1. Greet and choose lookup method**

The agent introduces itself as Sam from Brightpath Support and asks whether the caller would prefer to look up their account by email or by phone number.

**2. Collect the lookup value**

The agent asks for the email address or phone number and captures it exactly as provided.

**3. Fetch the customer record**

Based on the chosen method, either `GET /customers/email/{email}` or `GET /customers/phone/{phone}` retrieves the matching customer record. Phone numbers with a `+` prefix are URL-encoded before the request is made. If no customer is found, the agent lets the caller know and offers alternatives.

**4. Fetch conversation history**

`GET /customers/{id}/conversations` retrieves the full list of conversations associated with the customer. The most recent conversation is used to summarize the latest issue and its current status.

**5. Summarize and close**

The agent reads back the customer's name, account creation date (if available), total number of past conversations, and the most recent case summary. The caller is then asked if there is anything else they need help with.

## Kustomer API Calls

| Timing | Endpoint | Purpose |
|---|---|---|
| Post-collection | `GET /customers/email/{email}` | Look up customer by email |
| Post-collection | `GET /customers/phone/{phone}` | Look up customer by phone number |
| Post-collection | `GET /customers/{id}/conversations` | Retrieve conversation history |

## Setup

### 1. Get a Kustomer API token

In Kustomer: **Settings** → **Security** → **API Keys** → **Add API Key**. Grant the key `org.permission.customer.read` and `org.permission.conversation.read` permissions.

### 2. Install dependencies

```bash
pip install guava requests
```

### 3. Set environment variables

```bash
export GUAVA_AGENT_NUMBER="+1..."
export KUSTOMER_API_TOKEN="<your_api_token>"
```

### 4. Run

```bash
python -m examples.integrations.kustomer.customer_lookup
```

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `KUSTOMER_API_TOKEN` | Kustomer API token |
