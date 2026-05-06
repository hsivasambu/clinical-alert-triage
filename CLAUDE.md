# Project: Clinical Alert Triage Assistant

## Objective

Hybrid alert triage system:
- Rules = safety + baseline severity
- LLM = explainability (not decision authority)
- Human = final control

## Core Principles (non-negotiable)

- Rules define minimum severity floor
- LLM cannot downgrade critical alerts
- No clinical diagnosis or treatment suggestions
- Fallback to rules-only if LLM output is invalid/low confidence
- Every decision must be auditable

---

## MVP Scope (what to build now)

### Inputs

Simulated alerts in JSON:
- telemetry tachycardia
- low oxygen saturation
- infusion pump alarm
- nurse call escalation
- fall-risk alert
- sepsis screening

### Outputs (per alert)

- baseline severity (rules)
- final priority
- destination/team
- structured explanation
- confidence level
- rules vs AI indicator
- audit log entry

### Frontend

- alerts table
- alert detail panel
- explanation panel (primary focus)
- override + feedback

---

## System Flow

1. Alert ingestion (FastAPI `POST /alerts`)
2. Rules engine → baseline severity
3. LLM → structured explanation + uncertainty
4. Decision layer → enforce guardrails
5. UI display
6. Human accept/override
7. Audit logging

---

## Architecture Layers

### 1. Ingestion
- FastAPI endpoint
- JSON-based simulated alerts

### 2. Rules Engine (critical)

Examples:
- SpO2 < 88% → Critical
- HR > 130 → High
- repeat alert → escalate

### 3. LLM Explainability

Responsible for:
- summary
- rationale
- uncertainty
- human-readable reasoning

Not responsible for:
- final decisions
- diagnosis or treatment

### 4. Decision Layer
- enforce severity floor
- allow limited escalation
- fallback to rules-only if needed

### 5. Human Review
- accept / override
- feedback capture

### 6. Audit Layer

Store:
- alert input
- rule output
- LLM output
- final decision
- override actions

---

## Data Model (must follow)

### Alert
- alert_id, type, patient_id, unit, timestamp, vitals, repeat_count

### Rule Output
- baseline_priority
- matched_rules
- suggested_route

### LLM Output
- summary
- rationale
- factors
- uncertainty
- recommended_checks
- confidence

### Final Decision
- final_priority
- final_route
- explanation_mode
- override info

---

## Explainability Standard (core feature)

Every explanation must include:
1. Summary
2. Key factors
3. Routing rationale
4. Uncertainty
5. Rule trace
6. Verification guidance

---

## Technical Stack

### MVP (fast build)
- React + TypeScript
- FastAPI
- SQLite
- OpenAI API

### Scalable path
- PostgreSQL / DynamoDB
- AWS hosting
- SQS (optional)

---

## What matters most (priority order)

1. Explanation quality
2. Safety via rules
3. Clear architecture
4. Human-in-the-loop workflow

---

## Non-goals

- Clinical validation
- Real hospital integrations
- Autonomous AI decisions

---

## Reference Docs

- Full project brief: see /docs/project-brief.md
- MVP + architecture detail: see /docs/mvp-architecture.md

## Monorepo Layout

```
clinical-alert-triage/
  CLAUDE.md           # this file — project context for Claude Code
  README.md           # human-readable overview
  docs/
    project-brief.md  # full project brief
    mvp-architecture.md  # MVP architecture detail
  frontend/           # React + TypeScript UI
  backend/            # FastAPI + rules engine + LLM layer
  sample_data/        # simulated alert JSON files
  prompts/            # LLM prompt templates
```
