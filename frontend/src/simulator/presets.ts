import type { AlertType } from '../types'

/** Flat string representation of a simulator form - all numerics are strings for input control. */
export interface PresetFields {
  alert_type: AlertType
  source_system: string
  patient_id: string
  unit: string
  room: string
  bed: string
  device_type: string
  message_text: string
  repeat_count: string
  heart_rate: string
  spo2: string
  blood_pressure_systolic: string
  blood_pressure_diastolic: string
  respiratory_rate: string
  temperature: string
  prior_alerts_24h: string
  recent_medications: string
  fall_risk_score: string
  admission_reason: string
  code_status: string
  additional_context: string
}

const BASE: PresetFields = {
  alert_type: 'tachycardia',
  source_system: 'Demo-Simulator',
  patient_id: 'P-10042',
  unit: '3-West',
  room: '312',
  bed: 'A',
  device_type: '',
  message_text: '',
  repeat_count: '0',
  heart_rate: '',
  spo2: '',
  blood_pressure_systolic: '',
  blood_pressure_diastolic: '',
  respiratory_rate: '',
  temperature: '',
  prior_alerts_24h: '0',
  recent_medications: '',
  fall_risk_score: '',
  admission_reason: '',
  code_status: 'Full',
  additional_context: '',
}

export const ALERT_TYPE_LABELS: Record<AlertType, string> = {
  tachycardia: 'Tachycardia',
  low_spo2: 'Low SpO2',
  infusion_pump: 'Infusion Pump',
  nurse_call: 'Nurse Call',
  fall_risk: 'Fall Risk',
  sepsis: 'Sepsis Screen',
}

export const PRESETS: Record<AlertType, PresetFields> = {
  tachycardia: {
    ...BASE,
    alert_type: 'tachycardia',
    device_type: 'Cardiac Monitor',
    message_text: 'Sustained tachycardia - HR > 130 bpm',
    heart_rate: '138',
    spo2: '96',
    blood_pressure_systolic: '142',
    blood_pressure_diastolic: '88',
    respiratory_rate: '18',
    temperature: '37.2',
    admission_reason: 'Chest pain evaluation',
  },
  low_spo2: {
    ...BASE,
    alert_type: 'low_spo2',
    unit: 'ICU',
    room: '105',
    bed: 'B',
    device_type: 'Pulse Oximeter',
    message_text: 'SpO2 critically low - below 88%',
    heart_rate: '104',
    spo2: '85',
    blood_pressure_systolic: '98',
    blood_pressure_diastolic: '62',
    respiratory_rate: '26',
    temperature: '37.8',
    prior_alerts_24h: '2',
    admission_reason: 'Respiratory distress',
  },
  infusion_pump: {
    ...BASE,
    alert_type: 'infusion_pump',
    device_type: 'BD Alaris PCA',
    message_text: 'Occlusion alarm on primary IV line',
    heart_rate: '88',
    spo2: '97',
    blood_pressure_systolic: '128',
    blood_pressure_diastolic: '78',
    admission_reason: 'Post-op care',
    additional_context: JSON.stringify({ drug: 'heparin', rate_ml_hr: 20, line: 'central' }, null, 2),
  },
  nurse_call: {
    ...BASE,
    alert_type: 'nurse_call',
    source_system: 'Nurse-Call-Panel',
    message_text: 'Patient requesting assistance - bathroom',
    admission_reason: 'Hip replacement recovery',
  },
  fall_risk: {
    ...BASE,
    alert_type: 'fall_risk',
    device_type: 'Bed-Exit Sensor',
    message_text: 'Bed-exit sensor triggered - high fall risk patient',
    fall_risk_score: '68',
    recent_medications: 'lorazepam, oxycodone',
    prior_alerts_24h: '1',
    admission_reason: 'Orthopedic surgery',
  },
  sepsis: {
    ...BASE,
    alert_type: 'sepsis',
    unit: 'ICU',
    room: '108',
    bed: 'A',
    device_type: 'EHR-Screening',
    message_text: 'SIRS criteria positive - sepsis screening alert',
    heart_rate: '98',
    spo2: '94',
    blood_pressure_systolic: '102',
    blood_pressure_diastolic: '64',
    respiratory_rate: '24',
    temperature: '38.7',
    prior_alerts_24h: '3',
    recent_medications: 'vancomycin, piperacillin-tazobactam',
    admission_reason: 'Suspected pneumonia',
  },
}
