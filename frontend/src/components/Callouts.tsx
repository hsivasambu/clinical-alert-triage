import type { ReactNode } from 'react'

// Describes the demo itself; never carries alert data or generated text.
export function About({ children, label = 'About this section', id }: { children: ReactNode; label?: string; id?: string }) {
  return <div className="about" id={id}><span className="about-label" aria-hidden="true">ⓘ {label}</span><span className="sr-only">{label}: </span>{children}</div>
}

// ai: recorded AI narrative · system: rules-only explanation text · rules: deterministic rule output · input: observed alert data
export type OutputKind = 'ai' | 'system' | 'rules' | 'input'
export function Output({ kind, title, children }: { kind: OutputKind; title: string; children: ReactNode }) {
  return <div className={`output output-${kind}`}><p className="output-title">{title}</p><div className="output-body">{children}</div></div>
}

export const OUTPUT_KIND_LABELS: Record<OutputKind, string> = {
  ai: 'Model output',
  system: 'System output',
  rules: 'Rules engine output',
  input: 'Observed input',
}

export function OutputLegend() {
  return <div className="output-legend" aria-label="How to read this demo">
    <span className="legend-heading">How to read this demo</span>
    <span className="legend-item legend-about">ⓘ About: description of the demo</span>
    <span className="legend-item legend-ai">{OUTPUT_KIND_LABELS.ai}: AI-written text</span>
    <span className="legend-item legend-system">{OUTPUT_KIND_LABELS.system}: rules-only fallback text</span>
    <span className="legend-item legend-rules">{OUTPUT_KIND_LABELS.rules}: deterministic decision</span>
    <span className="legend-item legend-input">{OUTPUT_KIND_LABELS.input}: alert data as received</span>
  </div>
}
