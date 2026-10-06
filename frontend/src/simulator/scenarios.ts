import { PRESETS, type PresetFields } from './presets'
import { buildAlert, generateAlertId } from './buildAlert'

export interface Scenario { id: string; title: string; description: string; fields: PresetFields }
// Uses existing simulator input. Descriptions explain engineering behavior only.
export const SCENARIOS: Scenario[] = [
  { id: 'threshold', title: 'Rules-based routing',
    description: 'A heart-rate alert crosses a fixed threshold, so the rules set the priority and destination on their own. Follow the rule evidence, explanation, and human review.',
    fields: PRESETS.tachycardia },
  { id: 'ai-support', title: 'AI-supported decision',
    description: 'A single bathroom call is Low priority under the rules, but the patient has sedating medications, a high fall-risk score and earlier alerts today. The AI reviewer can raise the priority by one level when that context supports it; it can never lower it, and the router still picks the team. Needs the AI explanation service to be configured.',
    fields: {
      ...PRESETS.nurse_call,
      unit: '4-East Surgical',
      message_text: 'Patient reports feeling dizzy and is trying to get up to the bathroom alone',
      prior_alerts_24h: '2',
      recent_medications: 'lorazepam, oxycodone',
      fall_risk_score: '72',
      admission_reason: 'Hip replacement recovery',
    } },
  { id: 'repeat', title: 'Repeated call escalation',
    description: 'A nurse call with three repeats raises the priority under the rules. Accept or override to inspect the append-only review trail.',
    fields: { ...PRESETS.nurse_call, repeat_count: '3' } },
]

export function buildScenarioAlert(scenario: Scenario) {
  return buildAlert({ ...scenario.fields, alert_id: generateAlertId(), timestamp: new Date().toISOString() })
}
