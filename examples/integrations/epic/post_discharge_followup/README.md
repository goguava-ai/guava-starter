# Post-Discharge Followup — Epic Integration

An outbound voice agent that calls recently discharged patients to check on their recovery. It collects structured clinical observations — pain level, medication adherence, and any concerning symptoms — then posts them to Epic as an Observation resource for the care team to review.

## How It Works

**1. Reach the patient**

`reach_person()` routes the call to the patient and handles gatekeepers and voicemail. If the patient can't be reached, a caring voicemail is left asking them to call back.

**2. Collect recovery data**

Once connected, the agent collects four fields:
- `recovery_status` — patient's own words on how recovery is going
- `pain_level` — numeric scale 0–10
- `medication_adherence` — whether discharge medications are being taken as prescribed
- `concerning_symptoms` — optional; any fever, swelling, shortness of breath, or wound changes

**3. After the call — post an Observation to Epic**

`save_results()` posts a single `Observation` resource (LOINC `72166-2`, Post-discharge follow-up) with a `valueString` summarizing all four data points. The observation is linked to the patient and timestamped.

**4. Risk-based call close**

The agent's closing message branches based on the response:
- Pain level >= 7 or any concerning symptoms → flags the case for urgent clinical review and advises the patient to call 911 if their condition worsens.
- Otherwise → reassures the patient their responses have been recorded and the care team will follow up.

## Epic FHIR Calls

| Timing | Method | Resource | Purpose |
|---|---|---|---|
| Post-call | `POST` | `Observation` | Record recovery status, pain level, medication adherence, and symptoms |

## Setup

```bash
export GUAVA_AGENT_NUMBER="+1..."
export EPIC_BASE_URL="https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4"
export EPIC_ACCESS_TOKEN="..."
```

## Run

```bash
python -m examples.integrations.epic.post_discharge_followup \
  "+15551234567" \
  --name "Jane Doe" \
  --patient-id "pat456"
```

## Sample Output

```json
{
  "use_case": "post_discharge_followup",
  "patient_name": "Jane Doe",
  "patient_id": "pat456",
  "fields": {
    "recovery_status": "Feeling much better, still a little sore",
    "pain_level": 3,
    "medication_adherence": "yes",
    "concerning_symptoms": null
  }
}
```

The corresponding Epic Observation will have:

```
valueString: "Recovery: Feeling much better, still a little sore. Pain: 3/10. Meds as prescribed: yes. Concerning symptoms: None reported."
```
