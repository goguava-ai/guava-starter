# Appointment Booking

**Direction:** Inbound

Handles inbound calls from clients who want to book a personal training session or group fitness class at Peak Performance Studio.

## What it does

1. Greets the caller and collects their email address to look up their Mindbody client account.
2. Asks whether they want a personal training session or a group fitness class.
3. Presents available session types fetched live from `GET /appointment/bookableItems`.
4. Collects the caller's preferred date, time, and trainer/instructor preference.
5. Looks up the client record via `GET /client/clients`.
6. Books the appointment via `POST /appointment/addAppointment` or enrolls them in a class via `POST /class/addclienttoclass`.
7. Confirms the booking and lets the caller know a confirmation email is on its way.

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `MINDBODY_API_KEY` | Developer subscription key from the Mindbody developer portal |
| `MINDBODY_SITE_ID` | Your Mindbody business site ID |
| `MINDBODY_STAFF_TOKEN` | Staff user token from `POST /usertoken/issue` |

## Usage

```bash
python __main__.py
```
