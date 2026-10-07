import type { AlertIn } from '../types'
import { generateAlertId } from './buildAlert'
import examples from './examples.json'

export type ScenarioMode = 'rules' | 'ai'
export interface Scenario { id: string; mode: ScenarioMode; title: string; description: string; alert: Omit<AlertIn, 'alert_id' | 'timestamp'> }
export const MODE_LABELS: Record<ScenarioMode, string> = { rules: 'Rules-based routing', ai: 'AI-supported decision' }
// Shared with backend/tests/test_demo_examples.py, which checks every AI example escalates. Descriptions explain engineering behavior only.
export const SCENARIOS = examples as unknown as Scenario[]

export function buildScenarioAlert(scenario: Scenario): AlertIn {
  return structuredClone({ ...scenario.alert, alert_id: generateAlertId(), timestamp: new Date().toISOString() })
}
