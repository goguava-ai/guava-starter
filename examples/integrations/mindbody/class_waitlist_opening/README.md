# Class Waitlist Opening

**Direction:** Outbound

Notifies waitlisted clients that a spot has opened in a class, confirms whether they want it, and enrolls them on the spot.

## What it does

1. Verifies the spot is still available via `GET /class/classes` before dialing (race-condition guard).
2. Calls the client and attempts to reach them directly using `reach_person`.
3. Excitedly informs the client that their waitlisted spot is now available.
4. Asks if they want to claim the spot and how they'd like to pay (existing credits or at the studio).
5. If they accept, enrolls them immediately via `POST /class/addclienttoclass`, which triggers a confirmation email.
6. If they decline, asks whether to keep them on the waitlist or remove them, then calls `POST /class/removeClientFromClass` if requested.
7. Handles the edge case where the spot fills between the pre-check and the call connecting.
8. Falls back to an urgent voicemail if the client cannot be reached.

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `MINDBODY_API_KEY` | Developer subscription key from the Mindbody developer portal |
| `MINDBODY_SITE_ID` | Your Mindbody business site ID |
| `MINDBODY_STAFF_TOKEN` | Staff user token from `POST /usertoken/issue` |

## Usage

```bash
python __main__.py +14155550178 \
  --client-id "100000789" \
  --name "Priya Chandran" \
  --class-id 55321 \
  --class-name "Saturday Morning Yoga Flow" \
  --class-datetime "Saturday at 9:00 AM" \
  --instructor-name "Instructor Maya"
```
