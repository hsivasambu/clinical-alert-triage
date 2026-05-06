"""
Unit tests for rules_engine.evaluate().

Coverage:
  - Critical alert cases
  - Medium-priority cases
  - Repeat alert escalation
  - Missing / partial vital sign data
  - Routing behaviour (rule-suggested routes, not router overrides)
"""

import pytest
from models import AlertType, Priority, VitalSigns, RecentContext
from rules_engine import evaluate
from router import Routes
from tests.conftest import make_alert


# ===========================================================================
# Critical alert cases
# ===========================================================================

class TestCriticalAlerts:

    def test_spo2_below_88_is_critical(self):
        alert = make_alert(
            alert_type=AlertType.low_spo2,
            vital_signs=VitalSigns(spo2=85.0),
        )
        result = evaluate(alert)
        assert result.baseline_priority == Priority.critical
        assert "SPO2_LT_88" in result.matched_rules

    def test_spo2_at_87_is_critical(self):
        """Boundary: exactly 87 is below 88, must be Critical."""
        alert = make_alert(
            alert_type=AlertType.low_spo2,
            vital_signs=VitalSigns(spo2=87.0),
        )
        result = evaluate(alert)
        assert result.baseline_priority == Priority.critical

    def test_spo2_at_88_is_not_critical(self):
        """Boundary: exactly 88 is NOT below 88 — should be High."""
        alert = make_alert(
            alert_type=AlertType.low_spo2,
            vital_signs=VitalSigns(spo2=88.0),
        )
        result = evaluate(alert)
        assert result.baseline_priority == Priority.high
        assert "SPO2_88_92" in result.matched_rules

    def test_sepsis_two_sirs_criteria_is_critical(self):
        """HR > 90 + temp > 38.3 → 2 SIRS criteria → Critical."""
        alert = make_alert(
            alert_type=AlertType.sepsis,
            vital_signs=VitalSigns(heart_rate=110.0, temperature=39.0),
        )
        result = evaluate(alert)
        assert result.baseline_priority == Priority.critical
        assert "SEPSIS_SIRS_GTE_2" in result.matched_rules

    def test_sepsis_three_sirs_criteria_is_critical(self):
        """All three SIRS criteria → Critical."""
        alert = make_alert(
            alert_type=AlertType.sepsis,
            vital_signs=VitalSigns(heart_rate=110.0, temperature=39.0, respiratory_rate=22.0),
        )
        result = evaluate(alert)
        assert result.baseline_priority == Priority.critical
        assert "SEPSIS_SIRS_GTE_2" in result.matched_rules
        assert "SIRS_TEMP_ABNORMAL" in result.matched_rules
        assert "SIRS_HR_GT_90" in result.matched_rules
        assert "SIRS_RR_GT_20" in result.matched_rules

    def test_critical_spo2_route_is_rapid_response(self):
        alert = make_alert(
            alert_type=AlertType.low_spo2,
            vital_signs=VitalSigns(spo2=80.0),
        )
        result = evaluate(alert)
        assert result.suggested_route == Routes.RAPID_RESPONSE

    def test_critical_sepsis_route_is_rapid_response(self):
        alert = make_alert(
            alert_type=AlertType.sepsis,
            vital_signs=VitalSigns(heart_rate=95.0, temperature=38.5),
        )
        result = evaluate(alert)
        assert result.suggested_route == Routes.RAPID_RESPONSE


# ===========================================================================
# Medium-priority cases
# ===========================================================================

class TestMediumPriorityAlerts:

    def test_hr_110_to_130_is_medium(self):
        alert = make_alert(
            alert_type=AlertType.tachycardia,
            vital_signs=VitalSigns(heart_rate=120.0),
        )
        result = evaluate(alert)
        assert result.baseline_priority == Priority.medium
        assert "HR_110_130" in result.matched_rules

    def test_hr_exactly_110_is_not_medium(self):
        """Boundary: HR 110 is NOT in (110, 130] → falls to HR_GT_100 (Low)."""
        alert = make_alert(
            alert_type=AlertType.tachycardia,
            vital_signs=VitalSigns(heart_rate=110.0),
        )
        result = evaluate(alert)
        assert result.baseline_priority == Priority.low
        assert "HR_GT_100" in result.matched_rules

    def test_spo2_92_to_95_is_medium(self):
        alert = make_alert(
            alert_type=AlertType.low_spo2,
            vital_signs=VitalSigns(spo2=93.0),
        )
        result = evaluate(alert)
        assert result.baseline_priority == Priority.medium
        assert "SPO2_92_95" in result.matched_rules

    def test_fall_sensor_trigger_is_medium(self):
        alert = make_alert(alert_type=AlertType.fall_risk)
        result = evaluate(alert)
        assert result.baseline_priority == Priority.medium
        assert "FALL_SENSOR_TRIGGERED" in result.matched_rules

    def test_nurse_call_repeat_gte_3_is_medium(self):
        alert = make_alert(alert_type=AlertType.nurse_call, repeat_count=3)
        result = evaluate(alert)
        assert result.baseline_priority == Priority.medium
        assert "NURSE_CALL_REPEAT_GTE_3" in result.matched_rules

    def test_pump_battery_low_is_medium(self):
        alert = make_alert(
            alert_type=AlertType.infusion_pump,
            additional_context={"alarm_type": "battery_low"},
        )
        result = evaluate(alert)
        assert result.baseline_priority == Priority.medium
        assert "PUMP_BATTERY_LOW" in result.matched_rules

    def test_one_sirs_criterion_is_high_not_medium(self):
        """Single SIRS criterion → High (SEPSIS_SIRS_EQ_1), not Medium."""
        alert = make_alert(
            alert_type=AlertType.sepsis,
            vital_signs=VitalSigns(heart_rate=95.0),  # only HR > 90
        )
        result = evaluate(alert)
        assert result.baseline_priority == Priority.high
        assert "SEPSIS_SIRS_EQ_1" in result.matched_rules


# ===========================================================================
# Repeat alert escalation
# ===========================================================================

class TestRepeatAlertEscalation:

    def test_tachycardia_repeat_gte_3_escalates_to_high(self):
        """HR 105 (Low) + repeat=3 → High."""
        alert = make_alert(
            alert_type=AlertType.tachycardia,
            vital_signs=VitalSigns(heart_rate=105.0),
            repeat_count=3,
        )
        result = evaluate(alert)
        assert result.baseline_priority == Priority.high
        assert "TACHY_REPEAT_GTE_3" in result.matched_rules

    def test_tachycardia_repeat_escalation_routes_to_charge_nurse(self):
        """Repeat escalation should route to Charge Nurse (higher urgency than Bedside)."""
        alert = make_alert(
            alert_type=AlertType.tachycardia,
            vital_signs=VitalSigns(heart_rate=105.0),
            repeat_count=3,
        )
        result = evaluate(alert)
        assert result.suggested_route == Routes.CHARGE_NURSE

    def test_tachycardia_repeat_2_does_not_escalate(self):
        """repeat_count=2 is below the threshold of 3."""
        alert = make_alert(
            alert_type=AlertType.tachycardia,
            vital_signs=VitalSigns(heart_rate=105.0),
            repeat_count=2,
        )
        result = evaluate(alert)
        assert result.baseline_priority == Priority.low
        assert "TACHY_REPEAT_GTE_3" not in result.matched_rules

    def test_critical_spo2_with_repeat_stays_critical(self):
        """SPO2_LT_88 (Critical) + repeat=4 — floor holds at Critical."""
        alert = make_alert(
            alert_type=AlertType.low_spo2,
            vital_signs=VitalSigns(spo2=82.0),
            repeat_count=4,
        )
        result = evaluate(alert)
        assert result.baseline_priority == Priority.critical
        assert "SPO2_LT_88" in result.matched_rules

    def test_fall_risk_repeat_gte_2_escalates_to_high(self):
        alert = make_alert(alert_type=AlertType.fall_risk, repeat_count=2)
        result = evaluate(alert)
        assert result.baseline_priority == Priority.high
        assert "FALL_REPEAT_GTE_2" in result.matched_rules

    def test_pump_repeat_gte_3_escalates_to_high(self):
        alert = make_alert(
            alert_type=AlertType.infusion_pump,
            additional_context={"alarm_type": "battery_low"},
            repeat_count=3,
        )
        result = evaluate(alert)
        assert result.baseline_priority == Priority.high
        assert "PUMP_REPEAT_GTE_3" in result.matched_rules

    def test_repeat_escalation_beats_lower_priority_route(self):
        """When HR_110_130 (Medium, Bedside 5min) and TACHY_REPEAT_GTE_3 (High, Charge Nurse)
        both fire, the higher-priority repeat rule should dominate the route selection."""
        alert = make_alert(
            alert_type=AlertType.tachycardia,
            vital_signs=VitalSigns(heart_rate=120.0),
            repeat_count=3,
        )
        result = evaluate(alert)
        assert result.baseline_priority == Priority.high
        assert result.suggested_route == Routes.CHARGE_NURSE


# ===========================================================================
# Missing / partial vital sign data
# ===========================================================================

class TestMissingDataHandling:

    def test_tachycardia_no_vitals_returns_low_with_no_rule_matched(self):
        """No heart_rate + no repeat → only NO_RULE_MATCHED fires."""
        alert = make_alert(
            alert_type=AlertType.tachycardia,
            vital_signs=VitalSigns(),  # all None
        )
        result = evaluate(alert)
        assert result.baseline_priority == Priority.low
        assert "NO_RULE_MATCHED" in result.matched_rules

    def test_low_spo2_no_vitals_returns_low(self):
        alert = make_alert(
            alert_type=AlertType.low_spo2,
            vital_signs=VitalSigns(),
        )
        result = evaluate(alert)
        assert result.baseline_priority == Priority.low

    def test_sepsis_no_vitals_returns_low(self):
        """No vitals → 0 SIRS criteria → Low with SEPSIS_NO_SIRS_CRITERIA...
        actually NO_RULE_MATCHED since none fire."""
        alert = make_alert(
            alert_type=AlertType.sepsis,
            vital_signs=VitalSigns(),
        )
        result = evaluate(alert)
        # 0 SIRS criteria: SEPSIS_SIRS_GTE_2 and SEPSIS_SIRS_EQ_1 don't fire.
        # Individual criterion rules don't fire either (all vitals None).
        assert result.baseline_priority == Priority.low
        assert "NO_RULE_MATCHED" in result.matched_rules

    def test_sepsis_partial_vitals_one_criterion(self):
        """Only heart_rate provided → 1 SIRS criterion → High."""
        alert = make_alert(
            alert_type=AlertType.sepsis,
            vital_signs=VitalSigns(heart_rate=95.0),
        )
        result = evaluate(alert)
        assert result.baseline_priority == Priority.high
        assert "SIRS_HR_GT_90" in result.matched_rules

    def test_unknown_alert_type_returns_medium(self):
        """An unknown alert type produces a medium fallback (safe floor)."""
        # We can't construct an invalid AlertType via the enum, so test the
        # evaluate() fallback branch directly.
        from rules_engine import evaluate as _evaluate
        from unittest.mock import MagicMock
        mock_alert = MagicMock()
        mock_alert.alert_type = "totally_unknown_type"
        result = _evaluate(mock_alert)
        assert result.baseline_priority == Priority.medium
        assert "UNKNOWN_ALERT_TYPE" in result.matched_rules

    def test_rule_confidence_is_between_0_and_1(self):
        alert = make_alert(
            alert_type=AlertType.low_spo2,
            vital_signs=VitalSigns(spo2=85.0),
        )
        result = evaluate(alert)
        assert 0.0 <= result.rule_confidence <= 1.0

    def test_no_rule_matched_has_low_confidence(self):
        alert = make_alert(
            alert_type=AlertType.tachycardia,
            vital_signs=VitalSigns(),
        )
        result = evaluate(alert)
        assert result.rule_confidence == 0.5  # defined fallback


# ===========================================================================
# Routing behaviour (rules engine suggested_route)
# ===========================================================================

class TestRoutingBehaviour:

    def test_hr_gt_130_routes_to_bedside_immediate(self):
        alert = make_alert(
            alert_type=AlertType.tachycardia,
            vital_signs=VitalSigns(heart_rate=145.0),
        )
        result = evaluate(alert)
        assert result.suggested_route == Routes.BEDSIDE_IMMEDIATE

    def test_hr_110_130_routes_to_bedside_5min(self):
        alert = make_alert(
            alert_type=AlertType.tachycardia,
            vital_signs=VitalSigns(heart_rate=120.0),
        )
        result = evaluate(alert)
        assert result.suggested_route == Routes.BEDSIDE_5MIN

    def test_pump_occlusion_routes_to_bedside_immediate(self):
        alert = make_alert(
            alert_type=AlertType.infusion_pump,
            additional_context={"alarm_type": "occlusion"},
        )
        result = evaluate(alert)
        assert result.suggested_route == Routes.BEDSIDE_IMMEDIATE

    def test_pump_battery_low_routes_to_bedside_routine(self):
        alert = make_alert(
            alert_type=AlertType.infusion_pump,
            additional_context={"alarm_type": "battery_low"},
        )
        result = evaluate(alert)
        assert result.suggested_route == Routes.BEDSIDE_ROUTINE

    def test_single_nurse_call_routes_to_bedside_routine(self):
        alert = make_alert(alert_type=AlertType.nurse_call, repeat_count=0)
        result = evaluate(alert)
        assert result.suggested_route == Routes.BEDSIDE_ROUTINE

    def test_repeated_nurse_call_routes_to_charge_nurse(self):
        alert = make_alert(alert_type=AlertType.nurse_call, repeat_count=5)
        result = evaluate(alert)
        assert result.suggested_route == Routes.CHARGE_NURSE

    def test_fall_high_risk_score_routes_to_bedside_immediate(self):
        alert = make_alert(
            alert_type=AlertType.fall_risk,
            recent_context=RecentContext(fall_risk_score=65),
        )
        result = evaluate(alert)
        assert result.baseline_priority == Priority.high
        assert result.suggested_route == Routes.BEDSIDE_IMMEDIATE
        assert "FALL_HIGH_RISK_SCORE" in result.matched_rules
