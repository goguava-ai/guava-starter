# No-Show Follow-Up — Mindbody Integration

**Direction:** Outbound

FlexFit Studio calls members who no-showed to a class to check in, understand why they missed, and re-engage them. If the member answers, the agent asks how they're doing, whether they'd like to rebook, and if not, what class type might suit them better. If no one answers, a warm voicemail is left inviting them back.

## What it does

1. Calls the member and attempts to reach them by name using `reach_person`.
2. If connected: greets the member warmly, mentions the missed class by name and date, and asks if everything is okay — capturing the reason (just forgot, had an emergency, or no longer interested in this class type).
3. Asks whether they'd like to get back on the schedule.
4. **If they want to rebook:** encourages them and directs them to call back or book online at flexfitstudio.com.
5. **If they're not interested in that class type:** asks which class type they'd prefer (yoga, spin, HIIT, pilates, barre, boxing), logs their preference, encourages them to try it, and closes warmly.
6. Logs a note summarizing the interaction back to Mindbody via `POST /client/addclientformulae` (best-effort — the call completes even if this fails).
7. If no one answers: leaves a friendly, pressure-free voicemail inviting the member to rebook when they're ready.

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

python -m examples.integrations.mindbody.no_show_followup \
  "+15551234567" \
  --name "Alex Rivera" \
  --client-id "12345" \
  --class-name "Tuesday Morning Yoga" \
  --class-date "Tuesday, March 25 at 7:00 AM"
```

Use `--help` to see all arguments without placing a call:

```bash
python -m examples.integrations.mindbody.no_show_followup --help
```

## Arguments

| Argument | Description |
|---|---|
| `phone` | Member phone number in E.164 format (e.g. `+15551234567`) |
| `--name` | Full name of the member |
| `--client-id` | Mindbody client ID |
| `--class-name` | Name of the class the member missed |
| `--class-date` | Human-readable date/time of the missed class |

## Mindbody API Calls

| Timing | Method | Endpoint | Purpose |
|---|---|---|---|
| Post-call | `POST` | `/usertoken/issue` | Obtain staff token |
| Post-call | `POST` | `/client/addclientformulae` | Log follow-up note to member's record |
