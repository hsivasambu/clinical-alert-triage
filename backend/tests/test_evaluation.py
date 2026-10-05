from evaluate_demo import run_evaluation


def test_fixed_synthetic_contract_evaluation_is_offline_and_reproducible():
    result = run_evaluation()
    assert result["expectation_failures"] == []
    assert result["sample_sizes"] == {"distinct_alerts": 60, "invalid_inputs": 8, "model_fixtures": 17}
    assert len(result["by_alert_type"]) == 6
    m = result["metrics"]
    assert m["pipeline_runs"] == m["decision_authority_preserved"] == 1020
    assert m["known_unsupported_claims_accepted"] == 60
    assert m["adversarial_rejected"] < m["adversarial_runs"]
    assert result["manual_narrative_quality"]["assessed_by_human"] == 0
