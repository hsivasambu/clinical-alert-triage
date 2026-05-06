import { useState } from 'react'
import { api } from '../api/client'
import type { AlertIn, AlertType, TriageResult } from '../types'
import { ALERT_TYPE_LABELS, PRESETS, type PresetFields } from '../simulator/presets'

interface FormState extends PresetFields {
  alert_id: string
  timestamp: string
}

interface Props {
  onResult: (result: TriageResult) => void
  onClose: () => void
}

const ALERT_TYPES: AlertType[] = ['tachycardia', 'low_spo2', 'infusion_pump', 'nurse_call', 'fall_risk', 'sepsis']

function generateAlertId(): string {
  const ts = Date.now().toString(36).toUpperCase()
  const rand = Math.random().toString(36).slice(2, 6).toUpperCase()
  return `SIM-${ts}-${rand}`
}

function nowLocalDatetime(): string {
  const d = new Date()
  d.setSeconds(0, 0)
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const hours = String(d.getHours()).padStart(2, '0')
  const minutes = String(d.getMinutes()).padStart(2, '0')
  return `${year}-${month}-${day}T${hours}:${minutes}`
}

function buildDefaultForm(type: AlertType): FormState {
  return {
    ...PRESETS[type],
    alert_id: generateAlertId(),
    timestamp: nowLocalDatetime(),
  }
}

function parseNum(s: string): number | null {
  const n = parseFloat(s)
  return isNaN(n) ? null : n
}

function parseFormToAlert(form: FormState): AlertIn {
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

function validateForm(form: FormState): string | null {
  if (!form.alert_id.trim()) return 'Alert ID is required.'
  if (!form.patient_id.trim()) return 'Patient ID is required.'
  if (!form.unit.trim()) return 'Unit is required.'
  if (form.additional_context.trim()) {
    try {
      const parsed = JSON.parse(form.additional_context)
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
        return 'Additional context must be a JSON object.'
      }
    } catch {
      return 'Additional context must be valid JSON.'
    }
  }
  return null
}

export function AlertSimulator({ onResult, onClose }: Props) {
  const [form, setForm] = useState<FormState>(() => buildDefaultForm('tachycardia'))
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function applyPreset(type: AlertType) {
    setForm((prev) => ({
      ...buildDefaultForm(type),
      alert_id: prev.alert_id,
    }))
    setError(null)
  }

  function set(field: keyof FormState, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  async function handleSubmit() {
    const validationError = validateForm(form)
    if (validationError) {
      setError(validationError)
      return
    }

    setSubmitting(true)
    setError(null)
    try {
      const alert = parseFormToAlert(form)
      const result = await api.triageAlert(alert)
      onResult(result)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Submission failed.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div style={styles.overlay} onClick={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div style={styles.modal}>
        <div style={styles.modalHeader}>
          <div>
            <span style={{ fontWeight: 700, fontSize: 16 }}>Alert Simulator</span>
            <span style={{ marginLeft: 10, fontSize: 12, color: '#90caf9', background: '#1a4a7a', padding: '2px 8px', borderRadius: 4 }}>
              Rules are decision authority | LLM is explainability only
            </span>
          </div>
          <button onClick={onClose} style={styles.closeBtn} aria-label="Close">x</button>
        </div>

        <div style={styles.modalBody}>
          <div style={{ marginBottom: 20 }}>
            <label style={styles.sectionLabel}>Quick Presets</label>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {ALERT_TYPES.map((type) => (
                <button
                  key={type}
                  onClick={() => applyPreset(type)}
                  style={{
                    ...styles.presetBtn,
                    background: form.alert_type === type ? '#1a3a5c' : '#eef2f7',
                    color: form.alert_type === type ? 'white' : '#333',
                    borderColor: form.alert_type === type ? '#1a3a5c' : '#ccd',
                  }}
                >
                  {ALERT_TYPE_LABELS[type]}
                </button>
              ))}
            </div>
          </div>

          <FormSection title="Alert Identity">
            <FieldRow>
              <Field label="Alert ID *" hint="Auto-generated; must be unique">
                <div style={{ display: 'flex', gap: 6 }}>
                  <input
                    style={{ ...styles.input, flex: 1, fontFamily: 'monospace', fontSize: 12 }}
                    value={form.alert_id}
                    onChange={(e) => set('alert_id', e.target.value)}
                  />
                  <button
                    onClick={() => set('alert_id', generateAlertId())}
                    style={styles.secondaryBtn}
                    title="Regenerate ID"
                  >
                    Reroll
                  </button>
                </div>
              </Field>
              <Field label="Alert Type *">
                <select
                  style={styles.input}
                  value={form.alert_type}
                  onChange={(e) => {
                    const t = e.target.value as AlertType
                    setForm((prev) => ({ ...prev, alert_type: t, message_text: PRESETS[t].message_text }))
                  }}
                >
                  {ALERT_TYPES.map((t) => (
                    <option key={t} value={t}>{ALERT_TYPE_LABELS[t]}</option>
                  ))}
                </select>
              </Field>
            </FieldRow>

            <FieldRow>
              <Field label="Patient ID *">
                <input style={styles.input} value={form.patient_id} onChange={(e) => set('patient_id', e.target.value)} />
              </Field>
              <Field label="Source System">
                <input style={styles.input} value={form.source_system} onChange={(e) => set('source_system', e.target.value)} />
              </Field>
            </FieldRow>

            <FieldRow>
              <Field label="Unit *">
                <input style={styles.input} value={form.unit} onChange={(e) => set('unit', e.target.value)} />
              </Field>
              <Field label="Room">
                <input style={styles.input} value={form.room} onChange={(e) => set('room', e.target.value)} />
              </Field>
              <Field label="Bed">
                <input style={styles.input} value={form.bed} onChange={(e) => set('bed', e.target.value)} />
              </Field>
            </FieldRow>

            <FieldRow>
              <Field label="Timestamp">
                <input
                  style={styles.input}
                  type="datetime-local"
                  value={form.timestamp}
                  onChange={(e) => set('timestamp', e.target.value)}
                />
              </Field>
              <Field label="Repeat Count" hint=">=3 triggers escalation for most alert types">
                <input
                  style={styles.input}
                  type="number"
                  min="0"
                  value={form.repeat_count}
                  onChange={(e) => set('repeat_count', e.target.value)}
                />
              </Field>
            </FieldRow>

            <FieldRow>
              <Field label="Device Type">
                <input style={styles.input} value={form.device_type} onChange={(e) => set('device_type', e.target.value)} />
              </Field>
              <Field label="Message Text">
                <input style={styles.input} value={form.message_text} onChange={(e) => set('message_text', e.target.value)} />
              </Field>
            </FieldRow>
          </FormSection>

          <FormSection title="Vital Signs">
            <FieldRow>
              <Field label="Heart Rate (bpm)">
                <input style={styles.input} type="number" value={form.heart_rate} onChange={(e) => set('heart_rate', e.target.value)} placeholder="e.g. 95" />
              </Field>
              <Field label="SpO2 (%)">
                <input style={styles.input} type="number" value={form.spo2} onChange={(e) => set('spo2', e.target.value)} placeholder="e.g. 97" />
              </Field>
            </FieldRow>
            <FieldRow>
              <Field label="BP Systolic (mmHg)">
                <input style={styles.input} type="number" value={form.blood_pressure_systolic} onChange={(e) => set('blood_pressure_systolic', e.target.value)} placeholder="e.g. 120" />
              </Field>
              <Field label="BP Diastolic (mmHg)">
                <input style={styles.input} type="number" value={form.blood_pressure_diastolic} onChange={(e) => set('blood_pressure_diastolic', e.target.value)} placeholder="e.g. 80" />
              </Field>
            </FieldRow>
            <FieldRow>
              <Field label="Respiratory Rate (/min)">
                <input style={styles.input} type="number" value={form.respiratory_rate} onChange={(e) => set('respiratory_rate', e.target.value)} placeholder="e.g. 16" />
              </Field>
              <Field label="Temperature (C)">
                <input style={styles.input} type="number" step="0.1" value={form.temperature} onChange={(e) => set('temperature', e.target.value)} placeholder="e.g. 37.0" />
              </Field>
            </FieldRow>
          </FormSection>

          <FormSection title="Clinical Context">
            <FieldRow>
              <Field label="Prior Alerts (24h)">
                <input style={styles.input} type="number" min="0" value={form.prior_alerts_24h} onChange={(e) => set('prior_alerts_24h', e.target.value)} />
              </Field>
              <Field label="Fall Risk Score" hint="Morse scale; >=45 = high risk">
                <input style={styles.input} type="number" min="0" max="125" value={form.fall_risk_score} onChange={(e) => set('fall_risk_score', e.target.value)} placeholder="0-125" />
              </Field>
            </FieldRow>
            <FieldRow>
              <Field label="Admission Reason">
                <input style={styles.input} value={form.admission_reason} onChange={(e) => set('admission_reason', e.target.value)} />
              </Field>
              <Field label="Code Status">
                <input style={styles.input} value={form.code_status} onChange={(e) => set('code_status', e.target.value)} placeholder="e.g. Full, DNR" />
              </Field>
            </FieldRow>
            <FieldRow>
              <Field label="Recent Medications" hint="Comma-separated">
                <input
                  style={styles.input}
                  value={form.recent_medications}
                  onChange={(e) => set('recent_medications', e.target.value)}
                  placeholder="e.g. metoprolol, furosemide"
                />
              </Field>
            </FieldRow>
          </FormSection>

          <FormSection title="Additional Context (optional JSON)">
            <textarea
              style={{ ...styles.input, width: '100%', minHeight: 80, fontFamily: 'monospace', fontSize: 12, resize: 'vertical', boxSizing: 'border-box' }}
              value={form.additional_context}
              onChange={(e) => set('additional_context', e.target.value)}
              placeholder={'{\n  "key": "value"\n}'}
              spellCheck={false}
            />
          </FormSection>
        </div>

        <div style={styles.modalFooter}>
          {error && (
            <div style={{ flex: 1, color: '#c0392b', fontSize: 13, background: '#fdf2f2', border: '1px solid #f5c6c6', borderRadius: 4, padding: '6px 10px' }}>
              {error}
            </div>
          )}
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 10 }}>
            <button onClick={onClose} style={styles.cancelBtn} disabled={submitting}>Cancel</button>
            <button onClick={handleSubmit} style={styles.submitBtn} disabled={submitting}>
              {submitting ? 'Submitting...' : 'Submit Alert'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function FormSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 18 }}>
      <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 1, color: '#666', marginBottom: 8 }}>
        {title}
      </div>
      <div style={{ background: '#fafafa', border: '1px solid #e8e8e8', borderRadius: 6, padding: '12px 14px' }}>
        {children}
      </div>
    </div>
  )
}

function FieldRow({ children }: { children: React.ReactNode }) {
  return <div style={{ display: 'flex', gap: 12, marginBottom: 10, flexWrap: 'wrap' }}>{children}</div>
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div style={{ flex: 1, minWidth: 160 }}>
      <label style={{ display: 'block', fontSize: 12, color: '#555', marginBottom: 4, fontWeight: 500 }}>
        {label}
        {hint && <span style={{ color: '#999', fontWeight: 400, marginLeft: 5 }}>- {hint}</span>}
      </label>
      {children}
    </div>
  )
}

const styles = {
  overlay: {
    position: 'fixed' as const,
    inset: 0,
    background: 'rgba(0,0,0,0.45)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1000,
    padding: 16,
  },
  modal: {
    background: 'white',
    borderRadius: 10,
    width: '100%',
    maxWidth: 720,
    maxHeight: '92vh',
    display: 'flex',
    flexDirection: 'column' as const,
    boxShadow: '0 8px 40px rgba(0,0,0,0.25)',
  },
  modalHeader: {
    background: '#1a3a5c',
    color: 'white',
    padding: '14px 20px',
    borderRadius: '10px 10px 0 0',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    flexShrink: 0,
  },
  modalBody: {
    padding: '20px 24px',
    overflowY: 'auto' as const,
    flex: 1,
  },
  modalFooter: {
    padding: '12px 24px',
    borderTop: '1px solid #eee',
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    flexShrink: 0,
    background: '#fafafa',
    borderRadius: '0 0 10px 10px',
  },
  closeBtn: {
    background: 'none',
    border: 'none',
    color: 'white',
    fontSize: 18,
    cursor: 'pointer',
    padding: '0 4px',
    lineHeight: 1,
  },
  presetBtn: {
    padding: '6px 14px',
    borderRadius: 20,
    border: '1px solid',
    cursor: 'pointer',
    fontSize: 13,
    fontWeight: 500,
    transition: 'all 0.15s',
  },
  input: {
    width: '100%',
    padding: '6px 8px',
    border: '1px solid #d0d5dd',
    borderRadius: 5,
    fontSize: 13,
    outline: 'none',
    background: 'white',
    boxSizing: 'border-box' as const,
  },
  secondaryBtn: {
    padding: '6px 10px',
    border: '1px solid #ccc',
    borderRadius: 5,
    cursor: 'pointer',
    background: '#f5f5f5',
    fontSize: 12,
    flexShrink: 0,
  },
  cancelBtn: {
    padding: '8px 18px',
    border: '1px solid #ccc',
    borderRadius: 6,
    background: 'white',
    cursor: 'pointer',
    fontSize: 13,
  },
  submitBtn: {
    padding: '8px 22px',
    border: 'none',
    borderRadius: 6,
    background: '#1a3a5c',
    color: 'white',
    cursor: 'pointer',
    fontSize: 13,
    fontWeight: 600,
  },
  sectionLabel: {
    display: 'block' as const,
    fontSize: 11,
    fontWeight: 700,
    textTransform: 'uppercase' as const,
    letterSpacing: 1,
    color: '#666',
    marginBottom: 8,
  },
}
