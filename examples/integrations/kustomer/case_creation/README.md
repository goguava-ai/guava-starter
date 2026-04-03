# Case Creation — Kustomer Integration

An inbound voice agent that answers support calls, collects the caller's contact details and issue description, and opens a Kustomer conversation (case) on their behalf — all within the call.

## How It Works

**1. Greet and collect contact info**

The agent introduces itself as Jordan from Brightpath Support and gathers the caller's name and email address. The email is used to look up or create the customer record in Kustomer.

**2. Classify the issue**

The agent asks what type of issue they're experiencing (billing, technical, account-access, product-feedback, or other) and how severely it's affecting them (low, medium, high, or critical).

**3. Capture the issue summary**

The agent asks for a brief one-sentence description of the problem. This becomes the opening message body on the case.

**4. Look up or create the customer**

`GET /customers/email/{email}` searches for an existing Kustomer customer. If none is found, `POST /customers` creates a new record with the caller's name and email.

**5. Open a conversation**

`POST /conversations` opens a new voice conversation tagged with `guava` and `voice`. The case is set to `open` status.

**6. Post the opening message**

`POST /conversations/{id}/messages` records the issue type, severity, and summary as the first inbound message on the case.

**7. Confirm the case ID**

The agent reads back the conversation ID so the caller has it for future reference before hanging up.

## Kustomer API Calls

| Timing | Endpoint | Purpose |
|---|---|---|
| Post-collection | `GET /customers/email/{email}` | Look up existing customer by email |
| Post-collection | `POST /customers` | Create a new customer if not found |
| Post-collection | `POST /conversations` | Open a new support case |
| Post-collection | `POST /conversations/{id}/messages` | Record the issue details as the opening message |

## Setup

### 1. Get a Kustomer API token

In Kustomer: **Settings** → **Security** → **API Keys** → **Add API Key**. Grant the key `org.permission.conversation.create`, `org.permission.customer.create`, and `org.permission.customer.read` permissions.

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
python -m examples.integrations.kustomer.case_creation
```

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `KUSTOMER_API_TOKEN` | Kustomer API token |
