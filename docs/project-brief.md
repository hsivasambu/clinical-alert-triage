# Project Brief: Clinical Alert Triage Assistant

## Problem Statement

Hospital staff are overwhelmed by alert fatigue — a high volume of clinical alerts where many are low-urgency, making it easy to miss truly critical ones. Current systems lack explainability: even when an alert is flagged as high-priority, clinicians don't always know *why*, leading to delayed or inconsistent responses.

## Goal

Build a hybrid triage assistant that:
- Provides a reliable, rule-based severity baseline (safety anchor)
- Uses an LLM to generate clear, structured explanations for each alert (explainability layer)
- Keeps the human clinician in control of every final decision

The system is a decision-support tool, not an autonomous decision-maker.

## Users

- **Bedside nurses** — primary recipients of alert triage output
- **Charge nurses / rapid response teams** — act on escalated alerts
- **Clinical informatics / QA** — review audit logs and override patterns

## Alert Types in Scope (MVP)

| Alert Type           | Key Signal                          |
|----------------------|-------------------------------------|
| Telemetry tachycardia | Heart rate > threshold             |
| Low oxygen saturation | SpO2 below safe range              |
| Infusion pump alarm  | Pump fault or occlusion             |
| Nurse call escalation | Patient-initiated, repeated calls  |
| Fall-risk alert      | Sensor or assessment trigger        |
| Sepsis screening     | Multi-factor early warning          |

## Key Outputs per Alert

| Output               | Description                                          |
|----------------------|------------------------------------------------------|
| Baseline severity    | Rules-only priority (Critical / High / Medium / Low) |
| Final priority       | After LLM + decision layer guardrails                |
| Destination/team     | Who should respond and how quickly                   |
| Explanation          | Structured rationale (see Explainability Standard)   |
| Confidence level     | How certain the system is                            |
| Rules vs AI indicator | Which layer drove the decision                      |
| Audit log entry      | Immutable record of inputs, outputs, overrides       |

## Explainability Standard

Every explanation must include:
1. **Summary** — one-sentence plain-language description
2. **Key factors** — the specific vitals or signals that drove severity
3. **Routing rationale** — why this team/destination was chosen
4. **Uncertainty** — what the system does not know or cannot confirm
5. **Rule trace** — which rules fired and why
6. **Verification guidance** — what the nurse should check next

## Safety Constraints

- Rules define the minimum severity floor — immutable
- LLM may suggest escalation but cannot downgrade a critical alert
- If LLM output is malformed, low-confidence, or fails validation → fall back to rules-only
- No diagnosis, prognosis, or treatment recommendations from the LLM
- Every decision (including fallbacks and overrides) is audit-logged

## Success Criteria (MVP)

- All 6 alert types produce valid triage output end-to-end
- Explanation panel is clear and actionable to a non-technical clinician
- Rules engine correctly enforces severity floor in edge cases
- Override + feedback flow works in the UI
- Audit log captures all decisions with full traceability

## Non-Goals

- Clinical validation or regulatory approval
- Integration with real EHR or hospital systems
- Real-time streaming or high-throughput ingestion
- Autonomous AI decision-making
