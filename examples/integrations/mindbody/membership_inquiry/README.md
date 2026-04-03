# Membership Inquiry — Mindbody Integration

**Direction:** Inbound

A member calls FlexFit Studio to check on their membership status and remaining class credits. The agent looks up their account by phone number, fetches all active services from Mindbody, reads back a clear summary including remaining credits and expiration dates, then routes the member to the right next step.

## What it does

1. Greets the caller as Casey and collects their phone number.
2. Looks up the member in Mindbody via `GET /client/clients?SearchText=<phone>`. If no account is found, the call ends gracefully.
3. Fetches all client services via `GET /client/clientservices` and filters to currently active ones (memberships and class packs).
4. Reads back each active service with its remaining class count and expiration date. If there are no active services, the agent says so clearly.
5. Asks what the member would like to do next (book a class, cancel a booking, purchase more classes, or nothing).
6. Routes each choice to the appropriate outcome:
   - **Book a class:** directs them to the studio website or offers to have them call back.
   - **Cancel a booking:** advises them to call back with the specific class name or date.
   - **Purchase more classes:** offers to transfer them to the front desk.
   - **Nothing, all good:** thanks them and ends the call warmly.

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `MINDBODY_API_KEY` | Mindbody API key from the Developer Portal |
| `MINDBODY_SITE_ID` | Your Mindbody site ID |
| `MINDBODY_STAFF_USERNAME` | Staff username for obtaining access tokens |
| `MINDBODY_STAFF_PASSWORD` | Staff password |

## Usage

```bash
export GUAVA_AGENT_NUMBER="+1..."
export MINDBODY_API_KEY="..."
export MINDBODY_SITE_ID="..."
export MINDBODY_STAFF_USERNAME="..."
export MINDBODY_STAFF_PASSWORD="..."

python -m examples.integrations.mindbody.membership_inquiry
```

## Mindbody API Calls

| Timing | Method | Endpoint | Purpose |
|---|---|---|---|
| Mid-call | `POST` | `/usertoken/issue` | Obtain staff token for authenticated requests |
| Mid-call | `GET` | `/client/clients` | Look up member by phone number |
| Mid-call | `GET` | `/client/clientservices` | Fetch active memberships and class packs |
