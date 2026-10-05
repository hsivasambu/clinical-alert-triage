"""Local-only demonstration. It never calls a provider or writes the audit database.

python backend/demo_fallback.py --reason provider_timeout > local-demo.json
The JSON is explicitly labeled as a simulated outcome, not a live provider failure.
"""
import argparse
import json
from pathlib import Path

from decision_layer import apply
from llm_explainer import LLMOutcome, LLMRawOutput
from models import AlertIn
from rules_engine import evaluate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reason", choices=["llm_disabled", "provider_failure", "provider_timeout", "malformed_output", "schema_invalid", "low_confidence", "content_rejected"], default="provider_timeout")
    parser.add_argument("--fixture", type=Path, default=Path(__file__).resolve().parent.parent / "sample_data" / "alerts_edge_noisy_rules_only.json")
    args = parser.parse_args()
    data = json.loads(args.fixture.read_text(encoding="utf-8"))
    data["alert_id"] = "LOCAL-FALLBACK-DEMO"
    data["source_system"] = "Local fallback demonstration (simulated)"
    data.setdefault("additional_context", {})["local_demo"] = f"Simulated fallback: {args.reason}. No live provider call was made."
    alert = AlertIn.model_validate(data)
    output = None
    if args.reason == "low_confidence":
        output = LLMRawOutput(triggering_rule_ids=[], context_evidence_ids=["OBS_UNIT"], summary="Simulated rejected narrative.", rationale="Simulated rejected narrative.",
            factors_considered=["Simulated rejected narrative."], uncertainty_notes="Simulated rejected narrative.",
            recommended_checks=["Simulated rejected narrative."], confidence=0.1)
    result = apply(alert, evaluate(alert), LLMOutcome(output=output, fallback_reason=args.reason))
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
