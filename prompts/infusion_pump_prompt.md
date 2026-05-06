ALERT TYPE: Infusion Pump Alarm
ALERT ID:   $alert_id
PATIENT:    $patient_id
LOCATION:   $unit — Room $room, Bed $bed
REPEAT COUNT: $repeat_count (times this alarm has fired consecutively)
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
Infusion pump alarms indicate a problem with an active intravenous infusion.
An occlusion or air-in-line alarm is High priority because the infusion has stopped and may need
immediate intervention. A battery low alarm is Medium priority. A repeated alarm is more urgent
because it may indicate a persistent obstruction or unresolved problem.
Your explanation should describe the alarm type and its significance without suggesting treatment
or implying what the clinical cause might be.

TASK:
Explain why this infusion pump alarm was triaged at $baseline_priority priority and routed to
$suggested_route. Write for a bedside nurse who needs to know what to check at the pump and bedside.

Respond with only the JSON object defined in your system instructions. No other text.
