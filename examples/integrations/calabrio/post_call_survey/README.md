# Post-Call Survey — Calabrio Integration

An outbound voice agent that calls customers after a contact center interaction to collect a brief CSAT survey. Responses are submitted to Calabrio and linked to the original interaction for QM reporting.

## How It Works

**1. Initiate the outbound call**

Customer details and the Calabrio interaction ID are passed as CLI arguments. `reach_person()` ensures the correct person is on the line before starting the survey.

**2. Collect survey responses**

The agent collects:
- Overall satisfaction (1–5 scale)
- Agent performance rating (1–5 scale)
- Whether the issue was resolved
- Net Promoter Score (would recommend yes/no)
- Optional verbatim feedback

**3. Submit to Calabrio**

`submit_survey_response()` posts to `POST /api/surveys/responses`, linking the survey to the `interactionId` for quality reporting and agent scorecards.

**4. Adapt the closing**

Low scores or unresolved issues trigger a service recovery message; high scores get a warm thank-you.

## Calabrio API Calls

| Timing | Method | Endpoint | Purpose |
|---|---|---|---|
| Post-survey | `POST` | `/api/surveys/responses` | Submit CSAT survey response |

## Setup

```bash
export GUAVA_AGENT_NUMBER="+1..."
export CALABRIO_BASE_URL="https://mycompany.calabriocloud.com"
export CALABRIO_API_KEY="..."
```

## Run

```bash
python -m examples.integrations.calabrio.post_call_survey \
  +15551234567 \
  --name "Jane Doe" \
  --interaction-id "INT-20260330-00456" \
  --agent-name "Chris"
```

## Sample Output

```json
{
  "use_case": "post_call_survey",
  "customer_name": "Jane Doe",
  "interaction_id": "INT-20260330-00456",
  "overall_satisfaction": "5",
  "agent_score": "5",
  "issue_resolved": "yes",
  "would_recommend": "yes",
  "verbatim": "Chris was incredibly helpful and resolved my issue quickly."
}
```
