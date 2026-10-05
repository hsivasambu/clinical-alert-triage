# Local blog revision draft

**Review copy — not published.** Prepared 2026-10-05 against verified source `2a1b169`. Original: [clinical alert triage](https://blog.harry-sivasambu.com/blog/clinical-alert-triage). These are replacement sections rather than a reproduction of the full article. Keep the author's opening motivation and first-person tone; refresh workflow images/captions after checking deployed source.

## Editorial placement

Replace the demo invitation and authority/workflow description with these sections. Replace the feedback-learning claim with the feedback paragraph. Replace absolute content-safety/ambiguous confidence language with the limitations section. Add worked example/evidence before the conclusion. Preserve author-owned personal experience; do not turn it into a study or invent interviews.

---

## Try the working demo

[Open the portfolio demo](https://clinical-alert-triage-t7t1.vercel.app), [inspect the code](https://github.com/hsivasambu/clinical-alert-triage), or read the [walkthrough](https://github.com/hsivasambu/clinical-alert-triage#demo-walkthrough).

This is simulated data. Start with a threshold match, context-based routing or repeated input. Each demonstrates an engineering behavior without asking you to fill out the full simulator. Advanced customization is there if you want to explore all six types.

The explanation belongs to the recorded decision. Opening an existing alert does not generate a fresh AI answer. The demo also works without a model key: rules-only mode fills all six sections from input and matched rules. Hosting may lag the repository; the verification below describes tested source, not a claim that the deployment has been updated.

## Where I drew the boundary

I wanted each layer's responsibility to be easy to inspect. Rules assign priority. The router assigns destination. The model gets that completed decision and explains it. It cannot raise priority, lower it or choose another team.

That boundary goes further than protecting Critical from downgrades. A model-generated escalation would still be a decision. I have kept that job deterministic in both directions.

Human review has its own record. Acceptance stores the version and values being accepted. Override creates a new effective version without rewriting the original. The screen shows both, so a later reader can distinguish software output from human changes. A later override needs a new acceptance, even when it restores familiar values.

There is a limit here: the prototype lets a human lower even Critical. Reviewer names are typed labels, not authenticated identities. That demonstrates human control; it is not a finished clinical permissions policy.

Feedback is deliberately modest. Ratings, categories and comments are stored in audit history. They do not retrain the model, alter rules or automatically improve future explanations. A learning pipeline would be separate future work.

## Worked example: one observation, two visible decisions

Here is a synthetic documentation example I checked locally with the provider disabled:

```json
{
  "alert_id": "DOC-SPO2-001",
  "source_system": "Documentation-Simulator",
  "alert_type": "low_spo2",
  "patient_id": "SYNTHETIC-001",
  "unit": "ICU",
  "timestamp": "2026-10-05T12:00:00Z",
  "vital_signs": {"spo2": 85},
  "repeat_count": 0
}
```

`SPO2_LT_88` matches because 85 is below 88. System priority is Critical. The ICU keyword branch selects `ICU Team (Intensivist + Nurse)` instead of the rule's initial Rapid Response destination. Both choices come from code, not narrative.

With the provider disabled, the recorded explanation uses `rules_only` and `llm_disabled`. Its six sections explain observation, threshold, router branch and missing information. Absent heart rate or temperature is unavailable, not quietly normal. Verification guidance concerns source, units, timestamps and rule evidence, without diagnosis or treatment advice.

Initially the effective decision is Critical / ICU Team, version 0, unreviewed. In a deliberately synthetic review, overriding to High without a new route creates a version and retains the ICU route. The original Critical result stays intact. Accepting that version records High / ICU Team against it. Refreshing reloads saved history when backend storage persists. This demonstrates review mechanics, not advice to downgrade an alert.

## What the checks can and cannot establish

I validate nonblank narrative, supplied evidence IDs, recognized measurement claims and detected decision contradictions. Conservative checks also look for prohibited content. Rejection records a reason and selects deterministic explanation. Provider failures, timeouts, invalid schemas and low explanation estimates have distinct reasons too.

Those checks make failures visible. They do not make prose trustworthy by definition. A valid citation can sit beside an unsupported sentence; a phrase filter can miss a paraphrase. I included a case that gets through rather than hiding it behind a perfect-looking score.

Model confidence is a self-reported explanation estimate. A deterministic cap reduces its displayed value for sparse/noisy input. Neither number is a calibrated clinical probability. Old rule scores are manual weights, not measured reliability.

Audit provenance records rules/prompt versions and hashes, model identity when available, validation outcome, fallback reason, duration and correlation ID. That helps inspect a recorded run; it does not guarantee identical words on another call. Rejected raw provider text is not retained as explanation history.

## Engineering evidence, with the denominator visible

On 2026-10-05, source [`2a1b169`](https://github.com/hsivasambu/clinical-alert-triage/commit/2a1b169893d0c5e65ff37584ad7fe34d5082ab20) passed 211 backend, 43 UI, 16 local browser/layout and two real API integration tests, plus type checking/build. [Hosted CI](https://github.com/hsivasambu/clinical-alert-triage/actions/runs/37359198842) passed backend/frontend/integration. External model calls were disabled or mocked.

[Evaluation](https://github.com/hsivasambu/clinical-alert-triage/blob/main/docs/evaluation-report.md) combines 60 distinct alerts with 17 reused provider fixtures: 1,020 pipeline runs, plus eight invalid inputs. Expected priority **and routing** were preserved in 1,020/1,020. Final response schemas passed 1,020/1,020; six-section fallback was complete in 900/900.

Adversarial detection was 420/480, or 87.5%. The same unsupported nonnumeric assertion escaped in 60 reused runs. Accepted evidence references passed mechanical checks, but that did not establish complete narrative grounding. These are correlated software-contract cases, not independent live-model trials. I have collected zero human narrative ratings and claim neither clinical validation nor improved patient outcomes.

## Finished capabilities and future work

Implemented: example submission, explanation, acceptance/override, feedback and chronological audit history. Missing input, provider fallback, duplicate IDs and database failures are handled before publishing decisions. Narrow screens have a usable queue and full-width detail view.

Deployment still matters. Browser refresh retains reviews, but server restart requires persistent SQLite storage. The app bounds public writes and has no automatic retention expiry; it is designed for one process. A repository push alone does not create a persistent disk or update hosting.

Authenticated reviewer permissions, shared multi-instance state, broader semantic checks, human narrative assessment and real clinical integration remain future work. Those are substantial projects, not boxes I can tick because the prototype runs.

What I want this project to make visible is who owns a decision, what an explanation supports and what a reviewer can inspect afterwards. AI can be useful in that smaller role. Responsibility still needs to be explicit.

---

## Exact publication/deployment actions remaining

No publication or deployment was performed for this draft.

### Blog — separate author action

1. Review/approve replacements, especially override permissions, validator escapes and absent clinical/human-quality results, in the author's publishing workflow.
2. Apply them in the blog source/CMS at `/blog/clinical-alert-triage`. Remove old feedback-to-model, model-escalation and guaranteed-content-safety claims. Preserve original publication date; add an update date if the site supports it.
3. Update workflow graphics: deterministic routing before explanation; SQLite commit before queue publication. Take screenshots only after verifying deployed source.
4. Preview mobile/desktop formatting, JSON, result denominators and repository ↔ demo ↔ blog links. Publish only with separate authorization.

### Application — separate operator action

1. Select verified backend/frontend revision and review its CI before release; do not assume `main` is deployed.
2. In Render configure one worker, `LLM_ENABLED=false`, Vercel origin in `ALLOWED_ORIGINS`, documented budgets. Provision persistent writable disk; set absolute `DEMO_DB_PATH` with existing parent. Archive existing history before storage migration: mounting a disk does not migrate the ephemeral DB.
3. Require `/ready` 200 for readiness; use `/health` for liveness. Check proxy body/time limits and trusted client-address forwarding. Set provider billing limits separately before any live generation.
4. In Vercel set build-time `VITE_API_URL` to selected backend, root `frontend`, build `npm run build`, output `dist`. Redeploy both through hosting controls; do not reset history as a deployment shortcut.
5. Smoke-test synthetic example → six sections → accept/override → audit → refresh. Test retention across a controlled backend restart, CORS/readiness/error labels, and links. Record deployed revision; do not claim hosted persistence until that restart check passes.
