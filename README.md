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
3. Pick a quick scenario and click **Run example**, or use **Advanced customization** to open the full simulator.
4. Inspect the selected result:
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

- broader frontend automated test coverage
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

## Human review semantics

The original `final_priority` and `final_route` remain the system decision. `review_state` on alert list/detail and per-alert audit responses exposes the effective priority, route, decision version, and status separately.

- Version 0 identifies the original system decision. Each override ID identifies a new effective decision version; the latest override wins. An omitted route retains the previous effective route.
- Acceptances snapshot the current version, priority, and route. The UI sends the displayed version; a stale version returns 409 without recording acceptance. Repeated acceptances append records without changing the decision.
- Status starts `unreviewed`, becomes `overridden` after an override, and becomes `accepted` when the current version is accepted. A later override returns it to `overridden`, even if the values match an older accepted version. Feedback does not change status.
- Existing acceptance rows are preserved with unknown version/snapshot fields. They appear in history but do not imply acceptance of the current decision.
- History loads whenever an alert is selected, including after a browser reload. Drafts and messages reset on alert switches. Successful mutations update the queue/detail from the response; failed history refreshes offer a read-only retry and explicitly confirm the action was saved.

Run frontend regression tests with `npm test`. Backend tests default to an empty LLM API key; LLM unit tests use mocked provider responses.

## Recruiter-facing frontend

The desktop workspace keeps the queue beside an explanation-first alert view. Below 761px, selecting an alert opens a full-width detail view; Back returns to the queue and restores keyboard focus. The decision header distinguishes current human changes from the original deterministic system decision. Source metadata, observed context, and technical provenance are expandable. All six explanation sections remain visible even when narrative fields are unavailable; missing content is identified rather than fabricated.

Core components and dialog style definitions use `frontend/src/styles.css`. Readable rule labels in `frontend/src/ruleLabels.ts` are presentation copies of existing rule descriptions, not a second rules engine. Update these labels if rule descriptions change.

`npm test` runs the review regressions. `npm run test:browser` runs Playwright layout checks using installed Microsoft Edge, with mocked API responses and no LLM calls. Checks cover widths 320, 390, 768, 1024, and 1440; long text; keyboard selection and Back; review controls; loading, empty, error and retry states; and narrative/decision provenance. Screenshots are generated under `frontend/test-results/` and ignored by Git. `npm run build` verifies TypeScript and the production bundle.

## First-visit entry flow

The compact introduction identifies simulated portfolio data and explains the three responsibilities: rules assign priority/routing, AI supplies explanation only, and humans review. Repository links use the verified Git origin (`https://github.com/hsivasambu/clinical-alert-triage`); the project blog is linked alongside it.

Quick examples reuse existing simulator presets and the same alert serializer: deterministic threshold, ICU context routing, and repeated nurse-call escalation. Each click creates a fresh alert through `POST /alerts`; it does not replay a recorded AI response. **Advanced customization** preserves the full simulator. Explanations returned by the API are labeled as recorded with their decisions, including rules-only responses; opening an existing alert does not generate an explanation live.

The initial available telemetry example (or first available alert) opens automatically without moving keyboard focus away from the introduction. Subsequent selections and Back actions take precedence. A delayed initial queue response merges existing results and cannot discard or replace a visitor's newly run example.

Entry browser regressions cover the desktop/narrow-screen path from example submission through explanation, acceptance, and persistence after reload. Their API responses are mocked. All three generated scenario inputs were also checked against the real FastAPI endpoints using an isolated SQLite database and mocked-out LLM calls.

## Queue controls and accessibility

Search matches alert ID, patient ID, or unit without case sensitivity. Priority and review-status filters use the current effective human-reviewed decision. Severity-first ordering uses Critical, High, Medium, Low, then observed alert time newest first, then alert ID; newest-first ordering uses alert time and alert ID. Processing time does not affect queue ordering. Filtering a selected alert out clears its detail view; clearing filters does not silently reopen it. Running a quick/custom scenario clears queue filters so the newly selected result is visible.

The compact queue displays priority, readable alert name, patient/unit, alert age, and review status. Routing and secondary identifiers remain in the detail view. Known repository fixtures are identified by their IDs and observed timestamps and labeled historical rather than presented as fresh alerts. Details label alert time and processing time separately.

Simulator and audit dialogs use native modal isolation, labeled titles, explicit Tab wrapping, Escape dismissal, and focus restoration. UI regressions cover effective-value filtering, deterministic sorting, hidden-selection clearing, keyboard selection, and desktop/mobile dialog focus behavior.
