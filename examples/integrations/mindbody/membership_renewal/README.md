# Membership Renewal

**Direction:** Outbound

Calls clients whose memberships are nearing expiration to offer renewal options and capture their interest level.

## What it does

1. Fetches the client's account status and remaining credits via `GET /sale/clientaccount` and `GET /client/clients` before placing the call.
2. Calls the client and attempts to reach them directly using `reach_person`.
3. Opens with a personalized greeting that mentions their membership name, expiry date, and any remaining credits.
4. Asks whether they want to continue their membership.
5. If interested, presents monthly, quarterly (10% savings), and annual (20% savings) plan options.
6. If undecided or declining, gently asks about hesitations and captures a preferred callback time.
7. Sends a renewal follow-up email via `POST /client/sendautoemail` for interested or undecided clients.
8. Falls back to a concise voicemail if the client cannot be reached.

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `MINDBODY_API_KEY` | Developer subscription key from the Mindbody developer portal |
| `MINDBODY_SITE_ID` | Your Mindbody business site ID |
| `MINDBODY_STAFF_TOKEN` | Staff user token from `POST /usertoken/issue` |

## Usage

```bash
python __main__.py +13105550142 \
  --client-id "100000456" \
  --name "David Okafor" \
  --expiry-date "April 15th" \
  --membership-name "Unlimited Monthly"
```
