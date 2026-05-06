ALERT TYPE: Sepsis Screening
ALERT ID:   $alert_id
PATIENT:    $patient_id
LOCATION:   $unit — Room $room, Bed $bed
REPEAT COUNT: $repeat_count (times this screening has triggered consecutively)
DEVICE:     $device_type
MESSAGE:    $message_text

VITAL SIGNS:
$vitals_section

RECENT PATIENT CONTEXT:
$context_section

RULES ENGINE OUTPUT (these are the decisions — you are explaining them, not changing them):
  Baseline priority: $baseline_priority
  Suggested route:   $suggested_route
  Rule confidence:   $rule_confidence
  Rules that fired:
$matched_rules

CLINICAL CONTEXT FOR THIS ALERT TYPE:
This alert is based on SIRS (Systemic Inflammatory Response Syndrome) criteria derived from vital signs.
SIRS criteria used in this system: heart rate > 90 bpm, respiratory rate > 20 /min,
temperature > 38.3°C or < 36.0°C. Two or more criteria = Critical (Sepsis screen positive).
One criterion = High (elevated concern). The rules that fired above show which specific criteria were met.
Your explanation should describe which SIRS criteria were present in the vital signs and why
the combination led to this priority level. Do NOT diagnose sepsis, suggest a cause, or recommend
treatment. Explain only what the data shows and what the nurse should observe next.

TASK:
Explain why this sepsis screening alert was triaged at $baseline_priority priority and routed to
$suggested_route. Focus on the specific vital sign criteria that fired and what they indicate
in terms of urgency — for a nurse who will respond immediately.

Respond with only the JSON object defined in your system instructions. No other text.
