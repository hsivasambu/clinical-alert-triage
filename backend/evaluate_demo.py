"""Reproducible offline engineering evaluation. Never calls a provider or writes demo history."""
import argparse
import hashlib
import json
import logging
import os
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from pydantic import ValidationError
from decision_layer import apply
from explanation_contract import VALIDATION_VERSION, validate_narrative
from llm_explainer import LLMRawOutput, explain_with_outcome
from models import AlertIn, TriageResult
from prompt_builder import PROMPT_VERSION
from provenance import rules_version
from router import Routes, resolve_route
from rules_engine import evaluate

ROOT = Path(__file__).resolve().parent.parent
DATASET = ROOT / "evaluation" / "synthetic-v1.json"


def narrative(alert, rules, fixture):
    data = dict(summary="DECISION_FINAL records the existing deterministic decision.",
                rationale="The router records its destination in DECISION_FINAL.",
                factors_considered=["OBS_UNIT supplies recorded routing context."],
                uncertainty_notes="Source accuracy has not been independently verified.",
                recommended_checks=["Verify source timestamps, units and rule evidence before human review."],
                triggering_rule_ids=[id for id in rules.matched_rules if id != "NO_RULE_MATCHED"],
                context_evidence_ids=["OBS_UNIT"], confidence=.9)
    if fixture == "low": data["confidence"] = .1
    elif fixture == "missing": data.pop("summary")
    elif fixture == "blank": data["summary"] = "   "
    elif fixture == "empty_item": data["recommended_checks"] = [" "]
    elif fixture == "unknown_rule": data["triggering_rule_ids"] = ["FABRICATED_RULE"]
    elif fixture == "unknown_measurement":
        data["summary"] = "HR 999 bpm [OBS_HEART_RATE]"; data["context_evidence_ids"].append("OBS_HEART_RATE")
    elif fixture == "priority": data["summary"] = "Critical priority." if rules.baseline_priority.value != "Critical" else "Low priority."
    elif fixture == "route": data["rationale"] = Routes.RAPID_RESPONSE if resolve_route(alert, rules.baseline_priority, rules.suggested_route) != Routes.RAPID_RESPONSE else Routes.ICU_TEAM
    elif fixture == "proposal": data["recommended_checks"] = ["You should downgrade the priority."]
    elif fixture == "diagnosis": data["summary"] = "Diagnosis: infection."
    elif fixture == "treatment": data["recommended_checks"] = ["Administer antibiotics."]
    elif fixture == "uncovered": data["summary"] = "The sensor hardware is defective."  # Unsupported nonnumeric claim; designed limitation probe.
    return data


def run_evaluation(dataset=DATASET):
    raw_dataset = dataset.read_bytes().replace(b"\r\n", b"\n"); corpus = json.loads(raw_dataset)
    metrics = Counter(); reasons = Counter(); failures = []
    by_type = Counter(row["alert"]["alert_type"] for row in corpus["alerts"])
    tags = Counter(tag for row in corpus["alerts"] for tag in row["tags"])
    fake = MagicMock()
    with patch.dict(os.environ, {"OPENAI_API_KEY": "offline-mock", "LLM_ENABLED": "true"}), patch("openai.OpenAI", return_value=fake):
        for row in corpus["alerts"]:
            alert = AlertIn.model_validate(row["alert"]); rules = evaluate(alert)
            for model in corpus["model_fixtures"]:
                fixture = model["fixture"]; data = narrative(alert, rules, fixture)
                content = "{broken json" if fixture == "malformed" else json.dumps(data)
                schema_attempted = fixture not in {"disabled", "failure", "timeout"}
                if schema_attempted:
                    metrics["provider_schema_attempted"] += 1
                    try:
                        LLMRawOutput.model_validate_json(content); metrics["provider_schema_valid"] += 1
                    except ValidationError: pass
                fake.chat.completions.create.side_effect = RuntimeError("offline simulated failure") if fixture == "failure" else TimeoutError("offline simulated timeout") if fixture == "timeout" else None
                fake.chat.completions.create.return_value = SimpleNamespace(model="offline-evaluation-fixture", choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=content, refusal=None))])
                outcome = explain_with_outcome(alert, rules, "eval-" + row["id"] + "-" + model["id"], allow_provider=fixture != "disabled")
                result = apply(alert, rules, outcome)
                metrics["pipeline_runs"] += 1
                authority = result.final_priority.value == row["expected"]["priority"] and result.final_route == row["expected"]["route"]
                metrics["decision_authority_preserved"] += int(authority)
                metrics["final_schema_valid"] += int(TriageResult.model_validate_json(result.model_dump_json()) is not None)
                matched = result.explanation.fallback_reason == model["expected_reason"]
                metrics["fallback_expectation_matched"] += int(matched)
                if not authority or not matched: failures.append(row["id"] + "/" + model["id"])
                reasons[result.explanation.fallback_reason or "hybrid"] += 1
                if result.explanation.explanation_mode.value == "hybrid":
                    metrics["hybrid_records"] += 1
                    metrics["hybrid_passes_mechanical_evidence_checks"] += int(not validate_narrative(alert, rules, outcome.output))
                    if fixture == "uncovered": metrics["known_unsupported_claims_accepted"] += 1
                else:
                    metrics["fallback_records"] += 1
                    e = result.explanation
                    complete = all([e.summary.strip(), e.rationale.strip(), e.factors_considered, e.uncertainty_notes.strip(), e.rule_evidence, e.recommended_checks]) and e.rule_trace == rules.matched_rules
                    metrics["complete_fallback_records"] += int(complete)
                    if not complete: failures.append(row["id"] + "/incomplete-fallback")
                if model["adversarial"]:
                    metrics["adversarial_runs"] += 1
                    metrics["adversarial_rejected"] += int(result.explanation.explanation_mode.value == "rules_only")
        for row in corpus["invalid_inputs"]:
            metrics["invalid_input_cases"] += 1
            try: AlertIn.model_validate(row["alert"]); failures.append(row["id"] + "/unexpected-valid-input")
            except ValidationError: metrics["invalid_inputs_rejected"] += 1
    return dict(dataset_version=corpus["version"], dataset_sha256=hashlib.sha256(raw_dataset).hexdigest(), rules_version=rules_version(), prompt_version=PROMPT_VERSION, validation_version=VALIDATION_VERSION,
                sample_sizes=dict(distinct_alerts=len(corpus["alerts"]), invalid_inputs=len(corpus["invalid_inputs"]), model_fixtures=len(corpus["model_fixtures"])), by_alert_type=dict(by_type), tags=dict(tags), metrics=dict(metrics), fallback_counts=dict(reasons), expectation_failures=failures,
                manual_narrative_quality={"assessed_by_human": 0, "status": "Not assessed; see rubric. No automatic clinical-quality or reliability score."})


def report(result):
    m = result["metrics"]
    def fraction(a,b): return f"{m[a]}/{m[b]} ({100*m[a]/m[b]:.1f}%)"
    return f"""# Synthetic offline evaluation report

Dataset: `{result['dataset_version']}`; SHA-256 (LF-normalized file) `{result['dataset_sha256']}`.
Rules: `{result['rules_version']}`. Prompt: `{result['prompt_version']}`. Validator: `{result['validation_version']}`.

This is a deterministic software-contract evaluation with mocked provider responses. It is not clinical validation, a live LLM benchmark, a performance measurement, or a measured reliability estimate.

## Sample sizes and independence

{result['sample_sizes']['distinct_alerts']} distinct synthetic alerts across all six types, eight invalid inputs, and {result['sample_sizes']['model_fixtures']} reusable model-output fixtures yield {m['pipeline_runs']} pipeline runs. The same templates are reused across alerts; runs are strongly correlated and must not be presented as independent model samples. Threshold boundaries, repeated alerts, missing/noisy data, routing precedence and an untrusted-source instruction are included. Input expectations are checked-in software-policy examples, not clinical ground truth.

Alert counts: `{result['by_alert_type']}`. Tagged coverage: `{result['tags']}`.

## Deterministic metrics

| Metric and definition | Actual result |
| --- | --- |
| Decision-authority preservation: final priority **and route** equal the checked-in deterministic expectation despite provider content/failure | {fraction('decision_authority_preserved','pipeline_runs')} |
| Provider schema validity: raw JSON passes the strict LLM schema; excludes disabled/error/timeout cases with no payload | {fraction('provider_schema_valid','provider_schema_attempted')} |
| Final response schema validity: serialized pipeline records pass the response model | {fraction('final_schema_valid','pipeline_runs')} |
| Mechanical evidence checks on accepted hybrid records: valid cited IDs and recognized numeric values/units, plus configured phrase checks | {fraction('hybrid_passes_mechanical_evidence_checks','hybrid_records')} |
| Fallback behavior: actual structured reason equals each fixture's expected reason, including expected acceptance of the limitation probe | {fraction('fallback_expectation_matched','pipeline_runs')} |
| Complete fallback: all six sections present and rule trace preserved | {fraction('complete_fallback_records','fallback_records')} |
| Invalid input rejection before rules evaluation | {fraction('invalid_inputs_rejected','invalid_input_cases')} |
| Adversarial fixture detection: rejected explanation among deliberately adversarial model payloads | {fraction('adversarial_rejected','adversarial_runs')} |

Outcome counts: `{result['fallback_counts']}`. Expectation failures: **{len(result['expectation_failures'])}**.

## Grounding limitation demonstrated

{m['known_unsupported_claims_accepted']} accepted runs contain the same deliberately unsupported nonnumeric sentence, “The sensor hardware is defective.” Its evidence-ID arrays are valid and it evades the configured phrase checks. The mechanical evidence metric therefore **does not prove that every claim is grounded**. This is a known false negative, not hidden in a perfect score. No priority or routing change follows from that sentence. Other paraphrases, implicit causes, unusual formats, negation and multilingual text can also evade checks or produce false positives.

## Human narrative quality — separate assessment

**0 human-assessed narratives. No narrative-quality score is reported.** To assess a recorded sample, a human should separately record reviewer/date, case/model fixture ID, clarity (0–2), coverage of six sections (0–2), evidence faithfulness (0–2), distinction between observations/rules/human changes (0–2), and prohibited/speculative content (pass/fail), with notes. Preserve raw observations and record generation provenance. These rubric scores describe explanation quality; they cannot be treated as clinical reliability or decision validation. The unsupported-claim fixture should fail human evidence-faithfulness review.

## Reproduce

`python backend/evaluate_demo.py --check` runs offline, prints results and fails on unexpected contract outcomes. `python backend/evaluate_demo.py --report docs/evaluation-report.md` regenerates this report and `docs/evaluation-results.json`. No provider is called and no demo/audit database is written. Fixtures are local files, never a public fault-injection endpoint.
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)
    result = run_evaluation()
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(report(result), encoding="utf-8")
        args.report.with_name("evaluation-results.json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    if result["expectation_failures"]: raise SystemExit(1)

if __name__ == "__main__": main()
