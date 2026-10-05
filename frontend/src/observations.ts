// Units from the existing alert schema; formatting does not infer or evaluate values.
export const VITAL_LABELS: Record<string, [string, string]> = {
  heart_rate: ['Heart rate', 'bpm'], spo2: ['SpO₂', '%'],
  blood_pressure_systolic: ['Systolic blood pressure', 'mmHg'],
  blood_pressure_diastolic: ['Diastolic blood pressure', 'mmHg'],
  respiratory_rate: ['Respiratory rate', '/min'], temperature: ['Temperature', '°C'],
}
