# Insurance Discovery

**Direction:** Outbound

For patients with no insurance on file, this agent proactively calls ahead of an appointment to discover active plans using Stedi's Insurance Discovery API. Depending on the result, the agent either confirms the found plan with the patient, asks them to provide their insurance details, or discusses self-pay options.

## What it does

1. Submits a discovery request pre-call via `POST /insurance-discovery/check/v1` using the patient's name and date of birth
2. Polls `GET /insurance-discovery/check/v1/{discoveryId}` up to 6 times (5-second intervals) before the call connects
3. If plans are found: reaches the patient, presents the discovered plan, and asks them to confirm
4. If no plans are found: asks how they'd like to proceed (provide insurance, self-pay, or speak with billing)
5. If discovery times out: asks the patient for their insurance details directly

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `STEDI_API_KEY` | Stedi API key |
| `STEDI_PROVIDER_NPI` | Provider NPI number |
| `STEDI_PROVIDER_NAME` | Provider organization name (optional) |

## Usage

```bash
python -m examples.integrations.stedi.insurance_discovery \
  "+15551234567" --name "Jane Doe" --first-name Jane --last-name Doe --dob 1985-03-15
```
