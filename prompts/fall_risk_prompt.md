ALERT TYPE: Fall Risk
ALERT ID:   $alert_id
PATIENT:    $patient_id
LOCATION:   $unit — Room $room, Bed $bed
REPEAT COUNT: $repeat_count (times this sensor has triggered consecutively)
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
A fall risk alert is triggered by a bed-exit sensor or fall-risk assessment score crossing a threshold.
A single trigger is Medium priority. A high fall risk score (Morse scale ≥ 45) or repeated triggers
escalate to High priority. Fall risk is especially significant in units caring for patients with
neurological, post-surgical, or sedation-related mobility concerns.
Your explanation should describe why this alert is at its priority level based on the sensor trigger,
the repeat count, and the fall risk score if available — without speculating about patient behaviour
or suggesting clinical interventions.

TASK:
Explain why this fall risk alert was triaged at $baseline_priority priority and routed to
$suggested_route. Write for a bedside nurse who needs to assess the patient's safety immediately.

Respond with only the JSON object defined in your system instructions. No other text.
