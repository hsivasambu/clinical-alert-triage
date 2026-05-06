ALERT TYPE: Nurse Call
ALERT ID:   $alert_id
PATIENT:    $patient_id
LOCATION:   $unit — Room $room, Bed $bed
REPEAT COUNT: $repeat_count (times this call has fired consecutively)
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
A nurse call is a patient-initiated request for assistance.
A single call is Low priority. Three or more consecutive calls escalate to Medium priority
and are routed to the Charge Nurse because repeated calls may indicate unmet needs or distress.
Your explanation should describe the significance of the call pattern (especially if repeated)
without speculating about the patient's clinical condition or what they need.

TASK:
Explain why this nurse call was triaged at $baseline_priority priority and routed to
$suggested_route. Write for a bedside nurse or charge nurse who will respond.

Respond with only the JSON object defined in your system instructions. No other text.
