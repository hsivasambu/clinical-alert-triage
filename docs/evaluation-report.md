# Synthetic offline evaluation report

Dataset: `synthetic-v1`; SHA-256 (LF-normalized file) `9f5e828269e36d8548dd2afaa74a99c24e89d74ea2e8fc7c2899d2c7cada098f`.
Rules: `rules-v1-sha256:0236b7c72998ca97944ab6cccf811d4d7c681c2462f3a93325e5faf404693bf8`. Prompt: `explanation-contract-v2`. Validator: `evidence-contract-v1`.

This is a deterministic software-contract evaluation with mocked provider responses. It is not clinical validation, a live LLM benchmark, a performance measurement, or a measured reliability estimate.

## Sample sizes and independence

60 distinct synthetic alerts across all six types, eight invalid inputs, and 17 reusable model-output fixtures yield 1020 pipeline runs. The same templates are reused across alerts; runs are strongly correlated and must not be presented as independent model samples. Threshold boundaries, repeated alerts, missing/noisy data, routing precedence and an untrusted-source instruction are included. Input expectations are checked-in software-policy examples, not clinical ground truth.

Alert counts: `{'tachycardia': 12, 'low_spo2': 11, 'infusion_pump': 11, 'nurse_call': 6, 'fall_risk': 7, 'sepsis': 13}`. Tagged coverage: `{'boundary': 29, 'missing': 15, 'repeat': 12, 'noisy': 6, 'routing': 5, 'alarm': 5, 'combined': 2, 'adversarial_input': 1}`.

## Deterministic metrics

| Metric and definition | Actual result |
| --- | --- |
| Decision-authority preservation: final priority **and route** equal the checked-in deterministic expectation despite provider content/failure | 1020/1020 (100.0%) |
| Provider schema validity: raw JSON passes the strict LLM schema; excludes disabled/error/timeout cases with no payload | 600/840 (71.4%) |
| Final response schema validity: serialized pipeline records pass the response model | 1020/1020 (100.0%) |
| Mechanical evidence checks on accepted hybrid records: valid cited IDs and recognized numeric values/units, plus configured phrase checks | 120/120 (100.0%) |
| Fallback behavior: actual structured reason equals each fixture's expected reason, including expected acceptance of the limitation probe | 1020/1020 (100.0%) |
| Complete fallback: all six sections present and rule trace preserved | 900/900 (100.0%) |
| Invalid input rejection before rules evaluation | 8/8 (100.0%) |
| Adversarial fixture detection: rejected explanation among deliberately adversarial model payloads | 420/480 (87.5%) |

Outcome counts: `{'llm_disabled': 60, 'hybrid': 120, 'low_confidence': 60, 'provider_failure': 60, 'provider_timeout': 60, 'malformed_output': 60, 'schema_invalid': 180, 'evidence_mismatch': 120, 'contradiction': 120, 'content_rejected': 180}`. Expectation failures: **0**.

## Grounding limitation demonstrated

60 accepted runs contain the same deliberately unsupported nonnumeric sentence, “The sensor hardware is defective.” Its evidence-ID arrays are valid and it evades the configured phrase checks. The mechanical evidence metric therefore **does not prove that every claim is grounded**. This is a known false negative, not hidden in a perfect score. No priority or routing change follows from that sentence. Other paraphrases, implicit causes, unusual formats, negation and multilingual text can also evade checks or produce false positives.

## Human narrative quality — separate assessment

**0 human-assessed narratives. No narrative-quality score is reported.** To assess a recorded sample, a human should separately record reviewer/date, case/model fixture ID, clarity (0–2), coverage of six sections (0–2), evidence faithfulness (0–2), distinction between observations/rules/human changes (0–2), and prohibited/speculative content (pass/fail), with notes. Preserve raw observations and record generation provenance. These rubric scores describe explanation quality; they cannot be treated as clinical reliability or decision validation. The unsupported-claim fixture should fail human evidence-faithfulness review.

## Reproduce

`python backend/evaluate_demo.py --check` runs offline, prints results and fails on unexpected contract outcomes. `python backend/evaluate_demo.py --report docs/evaluation-report.md` regenerates this report and `docs/evaluation-results.json`. No provider is called and no demo/audit database is written. Fixtures are local files, never a public fault-injection endpoint.
