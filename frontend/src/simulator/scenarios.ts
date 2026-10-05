import { PRESETS, type PresetFields } from './presets'
import { buildAlert, generateAlertId } from './buildAlert'

export interface Scenario { id: string; title: string; description: string; fields: PresetFields }
// Uses existing simulator input. Descriptions explain engineering behavior only.
export const SCENARIOS: Scenario[] = [
  { id: 'threshold', title: 'Deterministic threshold',
    description: 'A telemetry example shows how a measured input triggers a priority rule. Follow the rule evidence, explanation, and human review.',
    fields: PRESETS.tachycardia },
  { id: 'context-route', title: 'Context-based routing',
    description: 'A critical-priority example in an ICU unit shows how the deterministic router uses unit context to choose a destination. AI cannot change that decision.',
    fields: PRESETS.low_spo2 },
  { id: 'repeat', title: 'Repeat escalation',
    description: 'A nurse-call example with three repeats shows how repeated input changes priority and routing. Accept or override to inspect the append-only review trail.',
    fields: { ...PRESETS.nurse_call, repeat_count: '3' } },
]

export function buildScenarioAlert(scenario: Scenario) {
  return buildAlert({ ...scenario.fields, alert_id: generateAlertId(), timestamp: new Date().toISOString() })
}
