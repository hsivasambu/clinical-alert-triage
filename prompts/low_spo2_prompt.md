ALERT TYPE: Low Oxygen Saturation (SpO2)
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

CLINICAL CONTEXT FOR THIS ALERT TYPE:
Oxygen saturation (SpO2) reflects how well the blood is carrying oxygen.
The priority thresholds are: SpO2 below 88% is Critical, 88–92% is High, 92–95% is Medium.
A Critical reading means the rules engine has flagged this as requiring immediate response.
Your explanation should describe the significance of the SpO2 reading in the context of the
thresholds and any other vital signs available — without suggesting a cause, diagnosis, or treatment.

TASK:
Explain why this low SpO2 alert was triaged at $baseline_priority priority and routed to
$suggested_route. Write for a bedside nurse who needs to act quickly and understand what to check.

Respond with only the JSON object defined in your system instructions. No other text.
