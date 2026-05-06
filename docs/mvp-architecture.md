# MVP Architecture: Clinical Alert Triage Assistant

## Overview

```
[Simulated Alert JSON]
        │
        ▼
[FastAPI: POST /alerts]
        │
        ▼
[Rules Engine]──────────────────────────────┐
        │                                   │
        │ baseline_priority                 │ (fallback path)
        │ matched_rules                     │
        │ suggested_route                   │
        ▼                                   │
[LLM Explainability Layer]                  │
        │                                   │
        │ summary, rationale,               │
        │ factors, uncertainty,             │
        │ recommended_checks, confidence    │
        ▼                                   │
[Decision Layer / Guardrails]◄──────────────┘
        │
        │ final_priority, final_route,
        │ explanation_mode
        ▼
[SQLite: Audit Log]
        │
        ▼
[React UI: Alert Table + Detail + Explanation Panel]
        │
        ▼
[Human: Accept / Override / Feedback]
        │
        ▼
[SQLite: Override Log]
```

---

## Layer 1 — Ingestion

**Endpoint:** `POST /alerts`

**Request body:**
```json
{
  "alert_id": "string",
  "type": "tachycardia | low_spo2 | infusion_pump | nurse_call | fall_risk | sepsis",
  "patient_id": "string",
  "unit": "string",
  "timestamp": "ISO8601",
  "vitals": {
    "heart_rate": 0,
    "spo2": 0,
    "blood_pressure": "string",
    "respiratory_rate": 0,
    "temperature": 0
  },
  "repeat_count": 0,
  "additional_context": {}
}
```

**Response:** Full triage result (see Decision Layer output).

---

## Layer 2 — Rules Engine

Deterministic Python module. No ML. No external calls.

**Rule examples:**

| Condition                    | Priority   | Route                      |
|------------------------------|------------|----------------------------|
| SpO2 < 88%                   | Critical   | Rapid Response Team        |
| SpO2 88–92%                  | High       | Bedside Nurse (immediate)  |
| HR > 130                     | High       | Bedside Nurse (immediate)  |
| HR 110–130                   | Medium     | Bedside Nurse (5 min)      |
| Repeat alert (count ≥ 3)     | Escalate   | Charge Nurse               |
| Sepsis ≥ 2 SIRS criteria     | Critical   | Rapid Response Team        |
| Infusion pump occlusion      | High       | Bedside Nurse (immediate)  |
| Fall sensor triggered        | Medium     | Bedside Nurse              |
| Nurse call (single)          | Low        | Bedside Nurse              |

**Output schema:**
```python
{
  "baseline_priority": "Critical | High | Medium | Low",
  "matched_rules": ["rule_id_1", "rule_id_2"],
  "suggested_route": "string"
}
```

---

## Layer 3 — LLM Explainability

**Model:** OpenAI GPT-4o (or GPT-4o-mini for cost)

**Prompt inputs:**
- Alert data (type, vitals, repeat_count, unit)
- Rules engine output (baseline_priority, matched_rules)

**Expected output (structured JSON):**
```json
{
  "summary": "string",
  "rationale": "string",
  "factors": ["string"],
  "uncertainty": "string",
  "recommended_checks": ["string"],
  "confidence": 0.0
}
```

**Validation:**
- All fields present and non-empty
- `confidence` between 0.0 and 1.0
- If validation fails → fallback to rules-only, log failure

---

## Layer 4 — Decision Layer / Guardrails

**Rules:**
1. `final_priority` cannot be lower than `baseline_priority`
2. LLM may suggest escalation (one level up max)
3. If LLM confidence < 0.5 → `explanation_mode = "rules_only"`
4. If LLM output invalid → `explanation_mode = "rules_only"`
5. `explanation_mode` values: `"hybrid"` | `"rules_only"`

**Output schema:**
```python
{
  "alert_id": "string",
  "final_priority": "Critical | High | Medium | Low",
  "final_route": "string",
  "explanation_mode": "hybrid | rules_only",
  "rule_output": { ... },
  "llm_output": { ... } | None,
  "timestamp": "ISO8601"
}
```

---

## Layer 5 — Audit Log

**Storage:** SQLite (MVP), PostgreSQL (scale)

**Tables:**

`alert_decisions`
- alert_id, patient_id, unit, type, timestamp
- baseline_priority, matched_rules, suggested_route
- llm_summary, llm_confidence, explanation_mode
- final_priority, final_route
- created_at

`override_log`
- override_id, alert_id, nurse_id (optional)
- original_priority, overridden_priority
- reason (free text), timestamp

---

## Layer 6 — Frontend (React + TypeScript)

**Pages / Components:**

| Component         | Purpose                                              |
|-------------------|------------------------------------------------------|
| `AlertTable`      | List of all alerts with priority badge + status     |
| `AlertDetail`     | Selected alert vitals + metadata                    |
| `ExplanationPanel`| Primary focus — structured LLM explanation          |
| `RuleTrace`       | Which rules fired, why                              |
| `OverrideForm`    | Accept / override + free-text reason                |
| `FeedbackBar`     | Thumbs up/down on explanation quality               |
| `AuditView`       | Read-only log of past decisions                     |

**API calls:**
- `POST /alerts` — submit new alert
- `GET /alerts` — list all triage results
- `GET /alerts/{id}` — get single triage result
- `POST /alerts/{id}/override` — submit override
- `POST /alerts/{id}/feedback` — submit explanation feedback

---

## Data Flow Summary

```
Alert JSON → Rules Engine → LLM (if available) → Guardrails → DB → UI → Human
                                                      ↑
                                              (fallback: skip LLM)
```

---

## Development Setup (planned)

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
uvicorn main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Environment variables
```
OPENAI_API_KEY=sk-...
DATABASE_URL=sqlite:///./clinical_triage.db
```

---

## File Structure (planned)

```
backend/
  main.py               # FastAPI app entry point
  rules_engine.py       # deterministic rules
  llm_explainer.py      # OpenAI integration
  decision_layer.py     # guardrails logic
  models.py             # Pydantic schemas
  database.py           # SQLite setup
  requirements.txt

frontend/
  src/
    components/
      AlertTable.tsx
      AlertDetail.tsx
      ExplanationPanel.tsx
      RuleTrace.tsx
      OverrideForm.tsx
      FeedbackBar.tsx
    pages/
      Dashboard.tsx
      AuditView.tsx
    api/
      client.ts
  package.json
  tsconfig.json

sample_data/
  alerts_tachycardia.json
  alerts_low_spo2.json
  alerts_infusion_pump.json
  alerts_nurse_call.json
  alerts_fall_risk.json
  alerts_sepsis.json

prompts/
  explainability_prompt.md
  system_prompt.md
```
