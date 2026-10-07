import type { AlertIn } from '../types'
import type { PresetFields } from './presets'

export interface SimulationFields extends PresetFields { alert_id: string; timestamp: string }

export function generateAlertId(): string {
  const ts = Date.now().toString(36).toUpperCase()
  const rand = Math.random().toString(36).slice(2, 6).toUpperCase()
  return `SIM-${ts}-${rand}`
}

function parseNum(value: string): number | null {
  if (!value.trim()) return null
  const n = Number(value)
  if (!Number.isFinite(n)) throw new Error('Measurements must be finite numbers; leave unavailable values blank.')
  return n
}
function parseCount(value: string): number {
  const n = parseNum(value) ?? 0
  if (!Number.isInteger(n) || n < 0) throw new Error('Counts must be non-negative whole numbers.')
  return n
}

export function buildAlert(form: SimulationFields): AlertIn {
  if (!form.timestamp || !Number.isFinite(Date.parse(form.timestamp))) throw new Error('A valid alert time is required.')
  if (!form.patient_id.trim() || !form.unit.trim()) throw new Error('Patient ID and unit are required.')
  const additionalContext: Record<string, unknown> = {}
  if (form.alert_type === 'infusion_pump') {
    if (form.alarm_type.trim()) additionalContext.alarm_type = form.alarm_type.trim()
    if (form.infusate.trim()) additionalContext.infusate = form.infusate.trim()
  }

  return {
    alert_id: form.alert_id.trim(),
    source_system: form.source_system || 'Demo-Simulator',
    alert_type: form.alert_type,
    patient_id: form.patient_id.trim(),
    unit: form.unit.trim(),
    room: form.room || null,
    bed: form.bed || null,
    timestamp: new Date(form.timestamp).toISOString(),
    vital_signs: {
      heart_rate: parseNum(form.heart_rate),
      spo2: parseNum(form.spo2),
      blood_pressure_systolic: parseNum(form.blood_pressure_systolic),
      blood_pressure_diastolic: parseNum(form.blood_pressure_diastolic),
      respiratory_rate: parseNum(form.respiratory_rate),
      temperature: parseNum(form.temperature),
    },
    message_text: form.message_text || null,
    device_type: form.device_type || null,
    repeat_count: parseCount(form.repeat_count),
    recent_context: {
      prior_alerts_24h: parseCount(form.prior_alerts_24h),
      recent_medications: form.recent_medications
        ? form.recent_medications.split(',').map((s) => s.trim()).filter(Boolean)
        : [],
      fall_risk_score: form.fall_risk_score.trim() ? parseCount(form.fall_risk_score) : null,
      admission_reason: form.admission_reason || null,
      code_status: form.code_status || null,
    },
    additional_context: additionalContext,
  }
}
