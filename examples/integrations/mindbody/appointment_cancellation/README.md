# Appointment Cancellation — Mindbody Integration

**Direction:** Inbound

A member calls FlexFit Studio to cancel an upcoming class, personal training session, or spa appointment. The agent identifies their account by phone number, locates their next booking, warns them if the cancellation is within the 12-hour late-cancel window, and processes the cancellation only after the member confirms.

## What it does

1. Greets the caller and collects their phone number and what they want to cancel (a class booking, a personal training session, or a spa appointment).
2. Looks up the member in Mindbody via `GET /client/clients?SearchText=<phone>`. If no account is found, the call ends with guidance to contact the front desk.
3. For class cancellations: fetches upcoming class visits via `GET /client/clientvisits` and identifies the soonest booking. For personal training and spa: fetches upcoming appointments via `GET /appointment/staffappointments`.
4. Presents the most upcoming booking (name/type, instructor, date/time) to the member for confirmation.
5. If the class or appointment starts within 12 hours, warns the member that a late cancellation fee may apply before asking them to confirm.
6. On confirmation, removes the member from the class via `POST /class/removeclientfromclass` (passing `LateCancel: true` if applicable), or cancels the appointment via `DELETE /appointment/cancelappointment`.
7. If the member chooses to keep their booking, ends the call with no changes made.

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

python -m examples.integrations.mindbody.appointment_cancellation
```

## Mindbody API Calls

| Timing | Method | Endpoint | Purpose |
|---|---|---|---|
| Mid-call | `POST` | `/usertoken/issue` | Obtain staff token for authenticated requests |
| Mid-call | `GET` | `/client/clients` | Look up member by phone number |
| Mid-call | `GET` | `/client/clientvisits` | Fetch upcoming class bookings (class flow) |
| Mid-call | `GET` | `/appointment/staffappointments` | Fetch upcoming appointments (PT/spa flow) |
| Post-confirm | `POST` | `/class/removeclientfromclass` | Cancel class booking |
| Post-confirm | `DELETE` | `/appointment/cancelappointment` | Cancel personal training or spa appointment |
