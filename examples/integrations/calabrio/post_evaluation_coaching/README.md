# Post-Evaluation Coaching — Calabrio Integration

An outbound voice agent that calls agents after a quality evaluation to share feedback, gather self-assessment, and schedule a coaching session in Calabrio. The evaluation is also marked as acknowledged.

## How It Works

**1. Initiate the outbound call with evaluation context**

Evaluation ID, score, and call date are passed as CLI arguments. `reach_person()` ensures the agent is reached before sharing sensitive performance data.

**2. Deliver feedback and collect self-assessment**

The agent shares the evaluation score, captures the agent's reaction, and asks for a self-assessment of the call.

**3. Gather coaching preference**

The agent asks when the agent would like to schedule coaching (this week, next week, within 30 days, or async via portal).

**4. Schedule the coaching session**

`schedule_coaching_session()` posts to `POST /api/qualitymanagement/coaching` with the proposed date and agent notes.

**5. Acknowledge the evaluation**

`update_evaluation_status()` patches `PATCH /api/qualitymanagement/evaluations/{id}` to mark it agent-acknowledged with any self-assessment notes.

## Calabrio API Calls

| Timing | Method | Endpoint | Purpose |
|---|---|---|---|
| Post-collect | `POST` | `/api/qualitymanagement/coaching` | Create coaching session |
| Post-collect | `PATCH` | `/api/qualitymanagement/evaluations/{id}` | Mark evaluation as acknowledged |

## Setup

```bash
export GUAVA_AGENT_NUMBER="+1..."
export CALABRIO_BASE_URL="https://mycompany.calabriocloud.com"
export CALABRIO_API_KEY="..."
```

## Run

```bash
python -m examples.integrations.calabrio.post_evaluation_coaching \
  +15551234567 \
  --name "Chris Johnson" \
  --agent-id "AG-1234" \
  --evaluation-id "EVAL-20260328-0078" \
  --score "82/100" \
  --call-date "2026-03-25"
```

## Sample Output

```json
{
  "use_case": "post_evaluation_coaching",
  "agent_name": "Chris Johnson",
  "evaluation_id": "EVAL-20260328-0078",
  "score": "82/100",
  "session_id": "COACH-20260331-0023",
  "proposed_date": "2026-03-31",
  "reaction": "expected it to be higher",
  "self_assessment": "I felt the call went well but could have de-escalated faster."
}
```
