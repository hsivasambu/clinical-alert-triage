import type { ExplanationOutput, Priority, RuleOutput } from '../types'

interface Props {
  explanation: ExplanationOutput
  ruleOutput: RuleOutput
  finalPriority: Priority
  finalRoute: string
}

const PRIORITY_COLOR: Record<Priority, string> = {
  Critical: '#c0392b',
  High: '#e67e22',
  Medium: '#d4ac0d',
  Low: '#27ae60',
}

export function ExplanationPanel({ explanation, ruleOutput, finalPriority, finalRoute }: Props) {
  const modeLabel = explanation.explanation_mode === 'hybrid' ? 'Hybrid Explanation' : 'Rules Only'
  const confidenceLabel = getConfidenceLabel(ruleOutput.rule_confidence)
  const showsEscalation = ruleOutput.baseline_priority !== finalPriority

  return (
    <div style={{ marginBottom: 20 }}>
      <h3 style={styles.sectionTitle}>Explanation</h3>
      <div style={styles.panel}>
        <div style={styles.summaryBlock}>
          <div style={styles.modeRow}>
            <span
              style={{
                ...styles.modeBadge,
                background: explanation.explanation_mode === 'hybrid' ? '#e3f2fd' : '#f3f4f6',
                color: explanation.explanation_mode === 'hybrid' ? '#1565c0' : '#666',
              }}
            >
              {modeLabel}
            </span>
            {explanation.explanation_mode === 'hybrid' && explanation.llm_confidence_estimate != null && (
              <span style={styles.subtleMeta}>
                LLM confidence {explanation.llm_confidence_estimate.toFixed(2)}
              </span>
            )}
          </div>

          <div style={styles.summaryText}>{explanation.summary}</div>

          {explanation.explanation_mode === 'rules_only' && (
            <div style={styles.rulesOnlyNotice}>
              LLM explanation unavailable. This triage is based on deterministic rules only.
            </div>
          )}
        </div>

        {explanation.factors_considered.length > 0 && (
          <PanelSection title="Key Factors">
            <div style={styles.factorGrid}>
              {explanation.factors_considered.map((factor) => (
                <div key={factor} style={styles.factorCard}>
                  {factor}
                </div>
              ))}
            </div>
          </PanelSection>
        )}

        <PanelSection title="Routing Rationale">
          <div style={styles.routingHero}>
            <div>
              <div style={styles.routeLabel}>Final route</div>
              <div style={styles.routeValue}>{finalRoute}</div>
            </div>
            <div
              style={{
                ...styles.priorityBadge,
                background: PRIORITY_COLOR[finalPriority],
              }}
            >
              {finalPriority}
            </div>
          </div>

          <div style={styles.routingMetaRow}>
            <MetaCard label="Baseline priority" value={ruleOutput.baseline_priority} />
            <MetaCard label="Rule confidence" value={confidenceLabel} />
          </div>

          {showsEscalation && (
            <div style={styles.escalationNote}>
              Priority changed from {ruleOutput.baseline_priority} to {finalPriority}.
            </div>
          )}

          {explanation.rationale && (
            <div style={styles.rationaleBlock}>{explanation.rationale}</div>
          )}
        </PanelSection>

        {explanation.uncertainty_notes && (
          <PanelSection title="Uncertainty">
            <div style={styles.uncertaintyBlock}>{explanation.uncertainty_notes}</div>
          </PanelSection>
        )}

        <PanelSection title="Rule Trace">
          <div style={styles.traceHint}>Deterministic rules fired by the rules engine</div>
          <div style={styles.traceWrap}>
            {explanation.rule_trace.map((rule) => (
              <code key={rule} style={styles.ruleChip}>
                {rule}
              </code>
            ))}
          </div>
        </PanelSection>

        {explanation.recommended_checks.length > 0 && (
          <PanelSection title="Verification Guidance">
            <div style={styles.checklist}>
              {explanation.recommended_checks.map((item, index) => (
                <div key={item} style={styles.checkItem}>
                  <div style={styles.checkIndex}>{index + 1}</div>
                  <div style={styles.checkText}>{item}</div>
                </div>
              ))}
            </div>
          </PanelSection>
        )}
      </div>
    </div>
  )
}

function PanelSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={styles.panelSection}>
      <div style={styles.panelSectionTitle}>{title}</div>
      {children}
    </div>
  )
}

function MetaCard({ label, value }: { label: string; value: string }) {
  return (
    <div style={styles.metaCard}>
      <div style={styles.metaLabel}>{label}</div>
      <div style={styles.metaValue}>{value}</div>
    </div>
  )
}

function getConfidenceLabel(confidence: number): string {
  if (confidence >= 0.85) return `High confidence (${confidence.toFixed(2)})`
  if (confidence >= 0.65) return `Moderate confidence (${confidence.toFixed(2)})`
  return `Low confidence (${confidence.toFixed(2)})`
}

const styles = {
  sectionTitle: {
    margin: '0 0 8px',
    fontSize: 13,
    textTransform: 'uppercase' as const,
    color: '#555',
    letterSpacing: 1,
  },
  panel: {
    background: '#fafafa',
    border: '1px solid #eee',
    borderRadius: 6,
    padding: '14px 16px',
  },
  summaryBlock: {
    marginBottom: 16,
    paddingBottom: 14,
    borderBottom: '1px solid #ececec',
  },
  modeRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    flexWrap: 'wrap' as const,
    marginBottom: 10,
  },
  modeBadge: {
    padding: '3px 9px',
    borderRadius: 999,
    fontSize: 11,
    fontWeight: 700,
    letterSpacing: 0.3,
  },
  subtleMeta: {
    fontSize: 12,
    color: '#777',
  },
  summaryText: {
    fontSize: 18,
    lineHeight: 1.45,
    fontWeight: 600,
    color: '#223',
  },
  rulesOnlyNotice: {
    marginTop: 10,
    fontSize: 12,
    color: '#666',
    background: '#f3f4f6',
    border: '1px solid #e5e7eb',
    borderRadius: 5,
    padding: '8px 10px',
  },
  panelSection: {
    marginBottom: 16,
  },
  panelSectionTitle: {
    fontSize: 11,
    fontWeight: 700,
    textTransform: 'uppercase' as const,
    letterSpacing: 1,
    color: '#666',
    marginBottom: 8,
  },
  factorGrid: {
    display: 'flex',
    flexWrap: 'wrap' as const,
    gap: 8,
  },
  factorCard: {
    background: 'white',
    border: '1px solid #dbe5f0',
    borderRadius: 8,
    padding: '8px 10px',
    fontSize: 13,
    fontWeight: 500,
    color: '#234',
    boxShadow: '0 1px 0 rgba(0,0,0,0.02)',
  },
  routingHero: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
    background: 'white',
    border: '1px solid #e5e7eb',
    borderRadius: 8,
    padding: '10px 12px',
    marginBottom: 10,
  },
  routeLabel: {
    fontSize: 11,
    textTransform: 'uppercase' as const,
    letterSpacing: 0.8,
    color: '#888',
    marginBottom: 3,
  },
  routeValue: {
    fontSize: 16,
    fontWeight: 700,
    color: '#1f2937',
  },
  priorityBadge: {
    color: 'white',
    borderRadius: 6,
    padding: '6px 10px',
    fontWeight: 700,
    fontSize: 12,
    minWidth: 66,
    textAlign: 'center' as const,
  },
  routingMetaRow: {
    display: 'flex',
    gap: 10,
    flexWrap: 'wrap' as const,
    marginBottom: 10,
  },
  metaCard: {
    background: '#f3f6fa',
    border: '1px solid #e2e8f0',
    borderRadius: 7,
    padding: '8px 10px',
    minWidth: 150,
  },
  metaLabel: {
    fontSize: 10,
    textTransform: 'uppercase' as const,
    letterSpacing: 0.8,
    color: '#7b8794',
    marginBottom: 2,
  },
  metaValue: {
    fontSize: 13,
    fontWeight: 600,
    color: '#243447',
  },
  escalationNote: {
    marginBottom: 10,
    fontSize: 12,
    color: '#1d4ed8',
    background: '#eff6ff',
    border: '1px solid #bfdbfe',
    borderRadius: 5,
    padding: '7px 9px',
  },
  rationaleBlock: {
    fontSize: 13,
    color: '#334155',
    lineHeight: 1.55,
  },
  uncertaintyBlock: {
    background: '#fff8e1',
    border: '1px solid #ffe082',
    borderRadius: 7,
    padding: '10px 12px',
    color: '#7c5a00',
    fontSize: 13,
    lineHeight: 1.5,
  },
  traceHint: {
    fontSize: 11,
    color: '#888',
    marginBottom: 8,
  },
  traceWrap: {
    display: 'flex',
    flexWrap: 'wrap' as const,
    gap: 8,
  },
  ruleChip: {
    background: '#f4f4f5',
    border: '1px solid #e4e4e7',
    borderRadius: 999,
    padding: '4px 9px',
    fontSize: 12,
    color: '#3f3f46',
  },
  checklist: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: 8,
  },
  checkItem: {
    display: 'flex',
    gap: 10,
    alignItems: 'flex-start',
    background: 'white',
    border: '1px solid #e5e7eb',
    borderRadius: 8,
    padding: '9px 10px',
  },
  checkIndex: {
    width: 22,
    height: 22,
    borderRadius: 999,
    background: '#1a3a5c',
    color: 'white',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: 12,
    fontWeight: 700,
    flexShrink: 0,
  },
  checkText: {
    fontSize: 13,
    color: '#243447',
    lineHeight: 1.45,
  },
}
