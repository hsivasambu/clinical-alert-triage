// Display labels from backend/rules_engine.py. These labels do not evaluate rules.
export const RULE_LABELS: Record<string, string> = {
  "HR_GT_130": "Heart rate > 130 bpm — significant tachycardia",
  "HR_110_130": "Heart rate 110–130 bpm — moderate tachycardia",
  "HR_GT_100": "Heart rate 100–110 bpm — mild tachycardia",
  "TACHY_REPEAT_GTE_3": "Tachycardia alert repeated ≥ 3 times — escalate to charge nurse",
  "SPO2_LT_88": "SpO₂ < 88% — critical hypoxaemia",
  "SPO2_88_92": "SpO₂ 88–92% — significant hypoxaemia",
  "SPO2_92_95": "SpO₂ 92–95% — mild hypoxaemia",
  "SPO2_REPEAT_GTE_3": "Low SpO₂ alert repeated ≥ 3 times — escalate",
  "PUMP_OCCLUSION": "Infusion pump occlusion alarm",
  "PUMP_AIR_IN_LINE": "Infusion pump air-in-line alarm",
  "PUMP_BATTERY_LOW": "Infusion pump battery low — non-urgent, swap battery",
  "PUMP_ALARM_GENERIC": "Infusion pump alarm — unrecognised alarm type",
  "PUMP_REPEAT_GTE_3": "Pump alarm repeated ≥ 3 times — escalate to charge nurse",
  "NURSE_CALL_REPEAT_GTE_3": "Nurse call repeated ≥ 3 times — escalate to charge nurse",
  "NURSE_CALL_SINGLE": "Single nurse call — routine response",
  "FALL_REPEAT_GTE_2": "Fall sensor triggered ≥ 2 times — escalate",
  "FALL_HIGH_RISK_SCORE": "Fall risk score ≥ 45 (high-risk threshold on Morse scale)",
  "FALL_SENSOR_TRIGGERED": "Fall sensor or bed-exit alarm triggered",
  "SEPSIS_SIRS_GTE_2": "Two or more SIRS criteria met — sepsis screen positive",
  "SEPSIS_SIRS_EQ_1": "One SIRS criterion met — elevated concern, monitor closely",
  "SIRS_TEMP_ABNORMAL": "Temperature outside normal range (> 38.3 °C or < 36.0 °C)",
  "SIRS_HR_GT_90": "Heart rate > 90 bpm (SIRS tachycardia criterion)",
  "SIRS_RR_GT_20": "Respiratory rate > 20 /min (SIRS tachypnoea criterion)"
}
export function ruleLabel(id: string): string { return RULE_LABELS[id] ?? id.replace(/_/g, " ").toLowerCase() }
