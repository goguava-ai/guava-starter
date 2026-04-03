# Chronic Disease Monitoring — Epic Integration

An outbound voice agent that calls patients with chronic conditions to collect remote health readings — blood pressure, blood glucose, and weight — and posts them to Epic as structured `Observation` resources. The agent fetches the patient's active conditions first and only asks for the vitals relevant to their diagnoses.

## How It Works

**1. Before the call — fetch active conditions to tailor the call**

The controller GETs `/Condition` for the patient and scans active diagnoses for keyword matches:
- Hypertension / cardiovascular → collect blood pressure
- Diabetes / glucose / A1C → collect blood glucose
- Obesity / weight management / BMI → collect weight

This means a diabetic patient isn't asked about blood pressure unless they also have hypertension, and vice versa. If the Epic fetch fails, all three vitals are collected as a safe default.

**2. Reach the patient**

`reach_person()` handles live answer detection. If unreachable, a voicemail asks the patient to call back or log readings in the portal.

**3. Collect only the relevant readings**

`begin_monitoring()` builds the checklist dynamically at runtime based on the condition flags set in `__init__`. It always appends two fields regardless of conditions:
- `symptoms` — any shortness of breath, dizziness, chest pain, swelling, or fatigue today
- `medication_adherence` — whether all medications were taken as prescribed

**4. After the call — post each reading as an Observation**

`save_results()` creates one `Observation` per collected metric, each with the correct LOINC code:
- Blood pressure → LOINC `55284-4` with systolic/diastolic components
- Blood glucose → LOINC `2339-0`
- Body weight → LOINC `29463-7`
- Symptoms + adherence summary → LOINC `72166-2` (always posted)

Observations with "not measured" are skipped.

**5. Symptom-based close**

If the patient reported any symptoms, the agent flags the responses for care team review and advises them to call 911 for severe symptoms.

## Epic FHIR Calls

| Timing | Method | Resource | Purpose |
|---|---|---|---|
| Pre-call | `GET` | `Condition` | Fetch active conditions to decide which vitals to collect |
| Post-call | `POST` | `Observation` (per metric) | Write each collected reading with the correct LOINC code |

## Setup

```bash
export GUAVA_AGENT_NUMBER="+1..."
export EPIC_BASE_URL="https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4"
export EPIC_ACCESS_TOKEN="..."
```

## Run

```bash
python -m examples.integrations.epic.chronic_disease_monitoring \
  "+15551234567" \
  --name "Jane Doe" \
  --patient-id "pat456"
```

## Sample Output

```json
{
  "use_case": "chronic_disease_monitoring",
  "conditions_monitored": {
    "hypertension": true,
    "diabetes": true,
    "weight_management": false
  },
  "fields": {
    "blood_pressure_systolic": "128",
    "blood_pressure_diastolic": "82",
    "blood_glucose": "145",
    "weight": null,
    "symptoms": "none",
    "medication_adherence": "yes"
  }
}
```

Three Epic Observations are created — blood pressure (composite), blood glucose, and the symptoms/adherence summary.
