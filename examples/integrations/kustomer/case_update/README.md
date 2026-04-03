# Case Update — Kustomer Integration

An inbound voice agent that allows customers to call in and add new information to an existing open support case in Kustomer. The update is recorded as an inbound voice message on the conversation.

## How It Works

**1. Greet and collect identifiers**

The agent introduces itself as Alex from Brightpath Support and asks the caller for their email address and case ID. Both are used to verify their identity and locate the correct conversation.

**2. Verify the customer**

`GET /customers/email/{email}` confirms the caller has a Kustomer account. If no account is found, the caller is informed and directed to verify their email.

**3. Verify the conversation**

`GET /conversations/{id}` fetches the conversation to confirm it exists and is still active (not done or snoozed). If the case is already closed, the caller is told to open a new case if their issue has recurred.

**4. Collect the update**

The agent asks the caller to describe what new information they'd like to add — additional symptoms, steps taken, error messages, or any other relevant details.

**5. Post the message**

`POST /conversations/{id}/messages` records the update as a new inbound voice message on the case, attributed to the caller by name.

**6. Confirm to the caller**

The agent confirms the update has been added and lets the caller know the support team will review it.

## Kustomer API Calls

| Timing | Endpoint | Purpose |
|---|---|---|
| Post-collection | `GET /customers/email/{email}` | Verify caller's account exists |
| Post-collection | `GET /conversations/{id}` | Verify the case exists and is open |
| Post-collection | `POST /conversations/{id}/messages` | Record the caller's update on the case |

## Setup

### 1. Get a Kustomer API token

In Kustomer: **Settings** → **Security** → **API Keys** → **Add API Key**. Grant the key `org.permission.customer.read`, `org.permission.conversation.read`, and `org.permission.message.create` permissions.

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
python -m examples.integrations.kustomer.case_update
```

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `KUSTOMER_API_TOKEN` | Kustomer API token |
