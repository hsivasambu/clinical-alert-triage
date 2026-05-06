# Clinical Alert Triage Assistant

**[Live Demo](https://clinical-alert-triage-t7t1.vercel.app)**

A hybrid clinical alert triage demo that combines deterministic rules, optional LLM-backed explainability, and human review.

The system is intentionally framed as decision support:

- Rules establish the minimum severity floor.
- The LLM contributes explanation content only.
- Humans can accept, override, and leave feedback.
- Every system and human action is auditable.

## Current Product State

The codebase now supports:

- FastAPI ingestion and triage at `POST /alerts`
- Data-driven routing and rule evaluation
- Optional OpenAI-backed explainability with `rules_only` fallback
- SQLite audit persistence for triage, acceptance, override, and feedback events
- React dashboard with:
  - alert queue
  - alert detail panel
  - dedicated explanation panel
  - alert simulator with presets
  - human review controls
  - audit log modal

## Architecture

```text
Simulated Alert JSON or UI Simulator
                |
                v
         FastAPI Ingestion
         POST /alerts
                |
                v
         Rules Engine
         baseline_priority
         matched_rules
         suggested_route
                |
                +------------------------------+
                |                              |
                v                              v
         LLM Explainer (optional)         SQLite Audit Log
         structured explanation           triage + human actions
                |
                v
         Decision Layer
         guardrails + explanation mode
                |
                v
         React Frontend
         queue + detail + explanation + review + audit
```

## Safety Contract

- `baseline_priority` from the rules engine is the severity floor.
- The LLM cannot downgrade severity or change routing authority.
- If the LLM is unavailable, malformed, or low confidence, the system falls back to `rules_only`.
- No diagnosis or treatment suggestions are produced.
- Human review actions are append-only and do not mutate the original triage record.

## Backend

### Key capabilities

- `rules_engine.py`: data-driven rule registries by alert type
- `router.py`: single source of truth for route strings and route ranking
- `llm_explainer.py`: structured OpenAI-backed explanation generation
- `decision_layer.py`: guardrail enforcement and final `TriageResult`
- `database.py`: SQLite storage for triage, overrides, feedback, and acceptances

### API surface

- `POST /alerts`
- `GET /alerts`
- `GET /alerts/{id}`
- `POST /alerts/{id}/accept`
- `POST /alerts/{id}/override`
- `POST /alerts/{id}/feedback`
- `GET /alerts/{id}/audit`
- `GET /audit`
- `GET /meta/feedback-categories`
- `GET /health`

## Frontend

The frontend is no longer a scaffold. It includes a working operator-facing demo workflow:

- alert queue table
- alert detail panel
- dedicated explanation panel with:
  - summary
  - key factors
  - routing rationale
  - uncertainty treatment
  - rule trace
  - verification guidance
- alert simulator modal with presets for:
  - tachycardia
  - low SpO2
  - infusion pump alarm
  - nurse call escalation
  - fall risk
  - sepsis
- human review panel for:
  - accept
  - override
  - explanation feedback
- audit log modal with filters and per-alert action counts

## Data Model

### Alert input

`AlertIn` includes:

- `alert_id`
- `source_system`
- `alert_type`
- `patient_id`
- `unit`
- `room`
- `bed`
- `timestamp`
- `vital_signs`
- `message_text`
- `device_type`
- `repeat_count`
- `recent_context`
- `additional_context`

### Rule output

- `baseline_priority`
- `matched_rules`
- `suggested_route`
- `rule_confidence`

### Explanation output

- `summary`
- `rationale`
- `factors_considered`
- `uncertainty_notes`
- `recommended_checks`
- `llm_confidence_estimate`
- `explanation_mode`
- `rule_trace`

### Human review records

- `AcceptanceRecord`
- `OverrideRecord`
- `FeedbackRecord`
- `AlertAudit`

## Running the Backend

Requires Python 3.11+.

```powershell
cd C:\Users\hsiva\OneDrive\Desktop\Clinical-Alert-Triaging\clinical-alert-triage\backend

python -m venv venv
.\venv\Scripts\pip.exe install -r requirements.txt
.\venv\Scripts\uvicorn.exe main:app --reload
```

Backend URLs:

- API: [http://localhost:8000](http://localhost:8000)
- Swagger docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- Health: [http://localhost:8000/health](http://localhost:8000/health)

### Optional LLM setup

The app runs fully in `rules_only` mode without OpenAI configured.

To enable hybrid explanations:

```powershell
cd C:\Users\hsiva\OneDrive\Desktop\Clinical-Alert-Triaging\clinical-alert-triage\backend
.\venv\Scripts\pip.exe install openai
$env:OPENAI_API_KEY="your-key-here"
.\venv\Scripts\uvicorn.exe main:app --reload
```

If the key is missing, invalid, or the model response is malformed or low confidence, the API falls back to `rules_only`.

## Running the Frontend

Requires Node 18+.

```powershell
cd C:\Users\hsiva\OneDrive\Desktop\Clinical-Alert-Triaging\clinical-alert-triage\frontend
npm install
npm run dev
```

Frontend URL:

- App: [http://localhost:5173](http://localhost:5173)

The Vite dev server proxies `/alerts`, `/audit`, `/health`, and `/meta` to the backend on port `8000`.

## Testing

### Backend

From `clinical-alert-triage/backend`:

```powershell
.\venv\Scripts\pytest.exe -q
```

Coverage in the backend test suite includes:

- rules engine behavior
- routing behavior
- explainability fallback and low-confidence handling
- guardrail preservation
- human review endpoints
- audit retrieval and filters

### Frontend

From `clinical-alert-triage/frontend`:

```powershell
npm run build
```

The frontend uses strict TypeScript and Vite production build as the main verification path.

## Demo Workflow

1. Start the backend.
2. Start the frontend.
3. Open the simulator and choose a preset.
4. Submit the alert and inspect:
   - baseline severity
   - final route
   - explanation mode
   - explanation panel content
5. Accept or override the result.
6. Leave explanation feedback.
7. Open the audit log and inspect the recorded actions.

## Project Structure

```text
clinical-alert-triage/
  backend/
    main.py
    models.py
    rules_engine.py
    router.py
    decision_layer.py
    llm_explainer.py
    prompt_builder.py
    database.py
    tests/
  frontend/
    src/
      api/
      components/
      simulator/
      types.ts
  prompts/
    system_prompt.md
    explainability_prompt.md
    tachycardia_prompt.md
    low_spo2_prompt.md
    infusion_pump_prompt.md
    nurse_call_prompt.md
    fall_risk_prompt.md
    sepsis_prompt.md
  sample_data/
  docs/
```

## What This Demo Proves

- Safety logic can remain deterministic while still using AI meaningfully.
- Explainability can be treated as a first-class UX surface rather than an afterthought.
- Human review can be made explicit, persistent, and auditable.
- Failure-tolerant AI integration is stronger than assuming the model is always available or correct.

## Known Gaps / Likely Next Work

- queue-level review status and effective post-override state
- stronger frontend automated test coverage
- richer audit drill-down and filtering
- evaluation views over override and feedback trends

## Deployment

The live demo is hosted on Render (backend) and Vercel (frontend).

### Backend — Render

- Service type: Web Service
- Root directory: `backend`
- Runtime: Python 3.11
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Environment variables: `OPENAI_API_KEY`, `ALLOWED_ORIGINS`
- Live URL: https://clinical-alert-triage-api.onrender.com
- API docs: https://clinical-alert-triage-api.onrender.com/docs

### Frontend — Vercel

- Framework: Vite
- Root directory: `frontend`
- Build command: `npm run build`
- Output directory: `dist`
- Environment variables: `VITE_API_URL`
- Live URL: https://clinical-alert-triage-t7t1.vercel.app

### Notes

- The backend seeds 6 sample alerts on first startup if the database is empty.
- Render's free tier has an ephemeral filesystem — submitted alerts do not persist across restarts, but sample alerts reseed automatically.
- A free UptimeRobot monitor pings `/health` every 5 minutes to keep the backend warm.
