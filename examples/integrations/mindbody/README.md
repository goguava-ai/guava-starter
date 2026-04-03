# Mindbody Integration

Voice agents that integrate with the [Mindbody API](https://developers.mindbodyonline.com/) to handle appointment booking, reminders, membership management, and class notifications for fitness and wellness businesses.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`appointment_booking`](appointment_booking/) | Inbound | Clients call to book a personal training session or group fitness class |
| [`appointment_reminder`](appointment_reminder/) | Outbound | Call clients the day before their appointment to confirm or cancel |
| [`membership_renewal`](membership_renewal/) | Outbound | Call clients with expiring memberships to offer renewal options |
| [`class_waitlist_opening`](class_waitlist_opening/) | Outbound | Notify waitlisted clients that a spot has opened and enroll them if they accept |

## Authentication

All examples use three Mindbody API headers:
- `API-Key`: Your Mindbody developer subscription key
- `SiteId`: Your Mindbody business site ID
- `Authorization: Bearer {StaffUserToken}`: Token obtained from `POST /usertoken/issue`

## Common Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `MINDBODY_API_KEY` | Developer subscription key from the Mindbody developer portal |
| `MINDBODY_SITE_ID` | Your Mindbody business site ID |
| `MINDBODY_STAFF_TOKEN` | Staff user token from `POST /usertoken/issue` |
