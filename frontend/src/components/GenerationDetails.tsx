import type { GenerationProvenance } from '../types'
export function GenerationDetails({ provenance: p }: { provenance?: GenerationProvenance | null }) {
  if (!p) return <p className="muted small">Generation provenance was not recorded for this legacy record.</p>
  return <dl className="metadata">{Object.entries(p).map(([key, value]) => <div className="metadata-row" key={key}><dt>{key.replace(/_/g, ' ')}</dt><dd>{Array.isArray(value) ? value.join(', ') || 'None recorded' : value == null ? 'Not recorded' : String(value)}</dd></div>)}</dl>
}
