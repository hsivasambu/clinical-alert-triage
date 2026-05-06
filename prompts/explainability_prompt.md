ALERT TYPE: $alert_type
ALERT ID:   $alert_id
PATIENT:    $patient_id
LOCATION:   $unit — Room $room, Bed $bed
REPEAT COUNT: $repeat_count (times this alert has fired consecutively)
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

TASK:
Generate a structured explanation of why this alert was triaged at $baseline_priority priority
and routed to $suggested_route. Your explanation must be written for a bedside nurse.

Respond with only the JSON object defined in your system instructions. No other text.
