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

## Complete rules-only explainability

Rules and the deterministic router remain the only sources of system priority and destination. A provider failure changes explanation mode, never the decision. Rules-only records now populate all six sections from recorded inputs, registered rule-condition metadata, and the router branch that selected the destination. Missing values are named as unavailable; verification guidance concerns source identifiers, units, timestamps, rule evidence, and human review rather than diagnosis or treatment. New records include `explanation_version: deterministic-v1` and structured `rule_evidence` alongside the original rule IDs.

`explanation.fallback_reason` appears in alert/list/detail responses, full audit JSON, and the audit-list `fallback_reason` column. Reasons are:

| Code | Meaning |
| --- | --- |
| `llm_disabled` | API key absent or blank; provider was not called |
| `provider_failure` | Provider/adapter error or unavailable SDK |
| `provider_timeout` | Provider timeout (15 seconds, SDK retries disabled) |
| `malformed_output` | Empty/missing response content or unparseable JSON |
| `schema_invalid` | JSON violates the required narrative schema, including empty text/items, non-finite confidence, or extra decision-authority fields |
| `low_confidence` | Validated/capped narrative confidence below 0.5; rejected narrative is discarded and its confidence is recorded |
| `content_rejected` | Provider refusal or content-filter finish signal |
| `not_supplied` | A direct local decision-layer caller supplied no LLM outcome; this does not guess a provider failure |

There is no semantic clinical-content classifier. Provider rejection signals are handled, but schema-valid narrative is not claimed to have passed diagnosis/treatment-content validation. Existing append-only decisions and narratives are not regenerated or backfilled. Legacy records have an unknown/null reason, labeled **Reason not recorded (legacy record)**. SQLite adds a nullable audit-list column without modifying old decision JSON.

### Missing and invalid input policy

Missing/null vital measurements remain unavailable and never satisfy numeric threshold rules. A provided zero is still a measurement, not an absent value. `rule_output.missing_fields` identifies unavailable inputs relevant to the alert's rule or routing checks; this can coexist with a matched repeat/base rule. Available-input rules still apply, so missing data never erases an already matched severity rule. An omitted repeat count uses the existing default 0 and is explicitly flagged as unavailable. Historical records lacking these provenance fields are not relabeled as fully observed.

`NO_RULE_MATCHED` is an explicit trace marker, not a normal-result rule. The existing default remains **Low → Bedside Nurse**, rule confidence **0.5**. The API exposes `evaluation_status: no_rule_matched`, and the UI calls out that this establishes neither normality nor safety. The explanation asks the human to verify missing/non-triggering input and review the default. No severity thresholds or routing precedence were changed. A higher missing-data floor would be a separate rule-policy change.

Ingestion requires nonblank alert/patient/source/unit identifiers, ISO 8601 alert timestamps with a timezone, finite numeric measurements, nonnegative integer counts (up to 1,000,000), and integer fall-risk scores 0–125. Numeric strings/booleans and unknown top-level/vital/context fields are rejected with 422 rather than silently coerced or ignored. Broad demo format bounds are HR 0–400 bpm, SpO2 0–100%, systolic 0–400 mmHg, diastolic 0–300 mmHg, respiratory rate 0–100/min, temperature 0–60 C. These are ingestion bounds, not clinical reference ranges or clinical validation. Optional measurements may be omitted; null containers and invalid supplied values are rejected. The simulator preserves blank measurements as null and rejects malformed numbers or fractional counts rather than silently dropping/truncating them.

`additional_context` preserves arbitrary JSON metadata, while rule/router inputs `alarm_type` and `infusate` are typed nullable strings. Null/missing/unknown pump alarm values take the existing generic pump rule; missing alarm values are flagged. The existing pump simulator preset now sends its recorded occlusion/heparin values with these recognized keys, rather than an unused `drug` key. Non-string alarm/infusion values and non-finite nested metadata are rejected before evaluation. Validation errors expose field locations and messages without reflecting unsafe raw values into response JSON.

### Local fallback demonstration (no public fault endpoint)

From the repository root, with the backend environment available:

```powershell
.\backend\venv\Scripts\python.exe backend/demo_fallback.py --reason provider_timeout
.\backend\venv\Scripts\python.exe backend/demo_fallback.py --reason low_confidence --fixture sample_data/alerts_low_spo2.json
```

The CLI emits a triage record labeled **Local fallback demonstration (simulated)** and **No live provider call was made**. It calls neither a provider nor the audit database. It supports the documented provider/fallback reasons solely as local demonstration options. There is no public fault-injection endpoint; submitting a top-level fallback-reason field is rejected. `frontend/e2e/fallback.json` is an explicitly labeled recorded local fixture generated by this tool, exercised at desktop and phone widths. API/audit persistence paths are separately covered with isolated mocked-provider tests. All backend suites default to an empty API key and make no external LLM calls.
