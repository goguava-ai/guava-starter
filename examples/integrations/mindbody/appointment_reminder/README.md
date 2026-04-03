# Appointment Reminder

**Direction:** Outbound

Calls clients the day before their appointment to confirm attendance or cancel, reducing no-shows at Peak Performance Studio.

## What it does

1. Looks up the client's upcoming appointment via `GET /appointment/staffAppointments` before placing the call.
2. Calls the client and attempts to reach them directly using `reach_person`.
3. Reminds them of their upcoming session details (service, trainer, time).
4. Asks whether they will attend or need to cancel.
5. If canceling, cancels the appointment via `POST /appointment/cancelAppointment` and asks about rescheduling interest.
6. If confirming, triggers a confirmation email via `POST /client/sendautoemail`.
7. Falls back to a voicemail if the client cannot be reached.

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `MINDBODY_API_KEY` | Developer subscription key from the Mindbody developer portal |
| `MINDBODY_SITE_ID` | Your Mindbody business site ID |
| `MINDBODY_STAFF_TOKEN` | Staff user token from `POST /usertoken/issue` |

## Usage

```bash
python __main__.py +12125550100 \
  --client-id "100000123" \
  --name "Sarah Mitchell" \
  --appointment-id 98765 \
  --appointment-datetime "9:00 AM" \
  --service-name "Personal Training (60 min)" \
  --staff-name "Coach Alex"
```
