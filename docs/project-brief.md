# Project brief: Clinical Alert Triage Assistant

[Repository](https://github.com/hsivasambu/clinical-alert-triage) · [Demo](https://clinical-alert-triage-t7t1.vercel.app) · [Blog](https://blog.harry-sivasambu.com/blog/clinical-alert-triage)

## Purpose and scope

This portfolio explores a software design question motivated by alert fatigue: can a fixed decision be explained and reviewed without granting a language model decision authority? It uses simulated data. It does not demonstrate reduced alert fatigue, improved clinical outcomes, measured reliability or clinician usability. Nurses, charge teams and informatics reviewers are hypothetical design audiences, not validated study participants.

Six simulated inputs are supported: telemetry tachycardia, low oxygen saturation, infusion pump alarm, nurse call escalation, fall-risk alert and sepsis screening. These labels do not establish diagnoses. Thresholds/destinations are software policy examples, not clinically validated ranges or response-time commitments.

## Implemented responsibilities

- **Observed input:** validated JSON, explicit missing measurements, source IDs and timezone-aware alert time.
- **Deterministic system:** rules determine priority; router precedence determines destination. The LLM cannot escalate, downgrade or reroute.
- **Explanation:** optional validated model narrative or complete deterministic fallback, recorded with evidence/provenance; all six sections visible.
- **Human review:** versioned acceptance/override, separate effective decision/status, append-only history and feedback.
- **Persistence:** commit originals before queue publication, reject duplicate IDs, reload reviews after refresh/restart when SQLite storage persists.

Original results expose `final_priority`, `final_route`, `rule_output`, `explanation`, `processed_at`, optional `provenance`. `review_state` separately exposes effective priority/route, version and `unreviewed`/`overridden`/`accepted` status. An accepted narrative is not a second decision authority.

Humans may lower even Critical here. Overrides require reason/reviewer label; there is no verified identity or clinical permission policy. Latest override wins; omitted route retains preceding effective route. Each override starts a new version requiring its own acceptance. Repeated acceptances/feedback append. Feedback is stored for inspection, not learning or rule changes.

## Explainability and uncertainty

Six sections: summary, triggering factors, routing rationale, uncertainty, readable rule trace, verification guidance. Contextual observations are separate from triggering rules; factual values render from validated input. Guidance concerns source/evidence review, not treatment.

LLM confidence is a self-reported explanation estimate with a completeness/noise cap, not clinical confidence. Legacy rule scores are manual weights. Missing measurements do not satisfy thresholds. `NO_RULE_MATCHED` retains Low → Bedside Nurse and establishes neither normality nor safety.

Validation rejects blank schema content, detected contradictions, incorrect evidence/numeric claims and configured prohibited phrases. Structured reasons distinguish disabled/provider/timeout/schema/confidence/content/evidence/contradiction fallback. Heuristics can miss unsupported claims; old narratives remain unchanged. See [architecture](mvp-architecture.md).

## Demonstrated engineering outcomes

At source `2a1b169` on 2026-10-05: 211 backend, 43 UI, 16 local browser/layout and two real API integration tests passed; type checking/build passed. [Hosted CI](https://github.com/hsivasambu/clinical-alert-triage/actions/runs/37359198842) passed backend/frontend/integration. Reproduction: [README](../README.md#verified-engineering-evidence).

[Offline evaluation](evaluation-report.md): 60 distinct alerts, 17 reused mocked outputs, eight invalid inputs. Expected system priority/route and final schemas passed 1,020/1,020 combinations; complete fallback 900/900. Adversarial detection was 420/480: one unsupported nonnumeric claim escaped in 60 correlated runs. Zero human narrative ratings. These are software-contract checks, not clinical validation or live-model quality measurements.

## Limits and future work

The public demo has bounded writes, no authentication and typed reviewer labels. One worker is required; SQLite needs a persistent disk for server-restart retention. No automatic retention expiry exists; operator archive/reset is separate. Hosted source may lag. [README](../README.md) covers setup, walkthrough and persistence.

Clinical validation, real integrations, reviewer permissions, multi-instance shared state and human narrative assessment remain future work. Autonomous clinical decisions and feedback-driven training are not implemented. [Blog replacements](blog-revision-draft.md) are local review material, not published.
