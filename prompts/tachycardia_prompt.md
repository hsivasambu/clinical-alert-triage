ALERT TYPE: Tachycardia (elevated heart rate)
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
Tachycardia means the heart rate is elevated beyond a normal threshold.
The priority was assigned based on the degree of elevation and whether the alert has repeated.
HR > 130 is high priority. HR 110–130 is medium priority. Repeat alerts increase urgency.
Your explanation should help the nurse understand the significance of the heart rate reading
and what bedside observations are most relevant — without suggesting a cause or treatment.

TASK:
Explain why this tachycardia alert was triaged at $baseline_priority priority and routed to
$suggested_route. Write for a bedside nurse who needs to know what to check and why it matters.

Respond with only the JSON object defined in your system instructions. No other text.
