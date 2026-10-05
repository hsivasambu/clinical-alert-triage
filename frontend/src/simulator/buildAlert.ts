import type { AlertIn } from '../types'
import type { PresetFields } from './presets'

export interface SimulationFields extends PresetFields { alert_id: string; timestamp: string }

export function generateAlertId(): string {
  const ts = Date.now().toString(36).toUpperCase()
  const rand = Math.random().toString(36).slice(2, 6).toUpperCase()
  return `SIM-${ts}-${rand}`
}

function parseNum(s: string): number | null {
  const n = parseFloat(s)
  return isNaN(n) ? null : n
}

export function buildAlert(form: SimulationFields): AlertIn {
  let additionalContext: Record<string, unknown> = {}
  if (form.additional_context.trim()) {
    try {
      const parsed = JSON.parse(form.additional_context)
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
        additionalContext = parsed as Record<string, unknown>
      }
    } catch {
      // validated before submit
    }
  }

  return {
    alert_id: form.alert_id.trim() || generateAlertId(),
    source_system: form.source_system || 'Demo-Simulator',
    alert_type: form.alert_type,
    patient_id: form.patient_id || 'P-UNKNOWN',
    unit: form.unit || 'General',
    room: form.room || null,
    bed: form.bed || null,
    timestamp: form.timestamp ? new Date(form.timestamp).toISOString() : new Date().toISOString(),
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
    repeat_count: parseInt(form.repeat_count, 10) || 0,
    recent_context: {
      prior_alerts_24h: parseInt(form.prior_alerts_24h, 10) || 0,
      recent_medications: form.recent_medications
        ? form.recent_medications.split(',').map((s) => s.trim()).filter(Boolean)
        : [],
      fall_risk_score: parseNum(form.fall_risk_score),
      admission_reason: form.admission_reason || null,
      code_status: form.code_status || null,
    },
    additional_context: additionalContext,
  }
}
