# Class Booking — Mindbody Integration

**Direction:** Inbound

A member calls FlexFit Studio to book a fitness class. The agent collects their phone number to pull up their Mindbody account, verifies they have active class credits, searches the live schedule for classes matching their type and time preference, presents the best match, and enrolls them on confirmation — all in a single phone call.

## What it does

1. Greets the caller and collects their phone number, desired class type (yoga, spin, HIIT, pilates, barre, boxing), preferred day, and preferred time of day (morning, afternoon, evening).
2. Looks up the member in Mindbody using `GET /client/clients?SearchText=<phone>`. If no account is found, the call ends with guidance to visit the front desk.
3. Fetches the member's active services via `GET /client/clientservices` to confirm they have remaining class credits. If there are none, the agent lets them know they need to purchase a package and offers to transfer to the front desk.
4. Searches the live schedule via `GET /class/classes` for the requested class type and day, then filters results by the preferred time window (morning: 5 AM–12 PM, afternoon: 12–5 PM, evening: 5–10 PM).
5. Presents the first matching class — name, instructor, date/time, and spots remaining — and asks the member to confirm.
6. On confirmation, enrolls the member via `POST /class/addenrollment` and confirms the booking with arrival instructions.

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

python -m examples.integrations.mindbody.class_booking
```

## Mindbody API Calls

| Timing | Method | Endpoint | Purpose |
|---|---|---|---|
| Mid-call | `POST` | `/usertoken/issue` | Obtain staff token for authenticated requests |
| Mid-call | `GET` | `/client/clients` | Look up member by phone number |
| Mid-call | `GET` | `/client/clientservices` | Verify active class credits |
| Mid-call | `GET` | `/class/classes` | Search available classes by date |
| Post-confirm | `POST` | `/class/addenrollment` | Enroll the member in the selected class |
