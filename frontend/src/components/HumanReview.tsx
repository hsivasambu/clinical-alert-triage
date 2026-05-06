import { useState } from 'react'
import { api } from '../api/client'
import type {
  AcceptanceRecord,
  AlertAudit,
  FeedbackRating,
  OverrideRecord,
  Priority,
  TriageResult,
} from '../types'
import { FEEDBACK_REASON_CATEGORIES, PRIORITIES } from '../types'

interface Props {
  result: TriageResult
  audit: AlertAudit | null
  reviewerId: string
  onReviewerIdChange: (id: string) => void
  onAuditUpdate: (audit: AlertAudit) => void
}

type Panel = 'none' | 'override' | 'feedback'

const PRIORITY_COLOR: Record<Priority, string> = {
  Critical: '#c0392b',
  High: '#e67e22',
  Medium: '#d4ac0d',
  Low: '#27ae60',
}

export function HumanReview({ result, audit, reviewerId, onReviewerIdChange, onAuditUpdate }: Props) {
  const [activePanel, setActivePanel] = useState<Panel>('none')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  const [overridePriority, setOverridePriority] = useState<Priority>(result.final_priority)
  const [overrideRoute, setOverrideRoute] = useState('')
  const [overrideReason, setOverrideReason] = useState('')

  const [feedbackRating, setFeedbackRating] = useState<FeedbackRating | null>(null)
  const [feedbackCategory, setFeedbackCategory] = useState('')
  const [feedbackComment, setFeedbackComment] = useState('')

  const latestOverride: OverrideRecord | undefined = audit?.overrides[audit.overrides.length - 1]
  const latestAcceptance: AcceptanceRecord | undefined = audit?.acceptances[audit.acceptances.length - 1]
  const hasFeedback = (audit?.feedback.length ?? 0) > 0

  async function refreshAudit() {
    const updated = await api.getAlertAudit(result.alert_id)
    onAuditUpdate(updated)
  }

  function showSuccess(msg: string) {
    setSuccessMsg(msg)
    setError(null)
    setTimeout(() => setSuccessMsg(null), 3000)
  }

  async function handleAccept() {
    if (!reviewerId.trim()) {
      setError('Reviewer ID is required.')
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      await api.acceptAlert(result.alert_id, reviewerId)
      await refreshAudit()
      showSuccess('Decision accepted and logged.')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Accept failed.')
    } finally {
      setSubmitting(false)
    }
  }

  async function handleOverrideSubmit() {
    if (!reviewerId.trim()) {
      setError('Reviewer ID is required.')
      return
    }
    if (!overrideReason.trim()) {
      setError('A reason is required for override.')
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      await api.submitOverride(result.alert_id, {
        reviewer_id: reviewerId,
        overridden_priority: overridePriority,
        overridden_route: overrideRoute.trim() || undefined,
        reason: overrideReason,
      })
      await refreshAudit()
      setActivePanel('none')
      setOverrideReason('')
      showSuccess('Override recorded in audit log.')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Override failed.')
    } finally {
      setSubmitting(false)
    }
  }

  async function handleFeedbackSubmit() {
    if (!reviewerId.trim()) {
      setError('Reviewer ID is required.')
      return
    }
    if (!feedbackRating) {
      setError('Please select a rating.')
      return
    }
    if (feedbackRating === 'not_helpful' && !feedbackCategory) {
      setError('Please select a reason category for not helpful feedback.')
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      await api.submitFeedback(result.alert_id, {
        reviewer_id: reviewerId,
        rating: feedbackRating,
        reason_category: feedbackCategory || undefined,
        comment: feedbackComment.trim() || undefined,
      })
      await refreshAudit()
      setActivePanel('none')
      setFeedbackRating(null)
      setFeedbackCategory('')
      setFeedbackComment('')
      showSuccess('Feedback recorded. Thank you.')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Feedback submission failed.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div style={{ marginBottom: 20 }}>
      <h3 style={styles.sectionTitle}>Human Review</h3>
      <div style={{ background: '#fafafa', border: '1px solid #eee', borderRadius: 6, padding: '12px 14px' }}>
        {latestOverride && (
          <div style={styles.overrideBadge}>
            <strong>Overridden</strong> by {latestOverride.reviewer_id} -
            {' '}
            <span style={{ color: PRIORITY_COLOR[latestOverride.original_priority] }}>
              {latestOverride.original_priority}
            </span>
            {' -> '}
            <span style={{ color: PRIORITY_COLOR[latestOverride.overridden_priority] }}>
              {latestOverride.overridden_priority}
            </span>
            <div style={{ fontSize: 11, color: '#888', marginTop: 2 }}>
              Reason: {latestOverride.reason}
            </div>
          </div>
        )}
        {latestAcceptance && !latestOverride && (
          <div style={styles.acceptedBadge}>
            Accepted by {latestAcceptance.reviewer_id} at{' '}
            {new Date(latestAcceptance.created_at).toLocaleTimeString()}
          </div>
        )}
        {hasFeedback && (
          <div style={{ fontSize: 12, color: '#666', marginBottom: 10 }}>
            Feedback recorded ({audit!.feedback.length} submission{audit!.feedback.length !== 1 ? 's' : ''})
          </div>
        )}

        <div style={{ marginBottom: 12 }}>
          <label style={styles.label}>Reviewer ID</label>
          <input
            style={{ ...styles.input, maxWidth: 220 }}
            value={reviewerId}
            onChange={(e) => { onReviewerIdChange(e.target.value); setError(null) }}
            placeholder="e.g. Dr. Smith"
          />
        </div>

        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: activePanel !== 'none' ? 14 : 0 }}>
          <button
            onClick={handleAccept}
            disabled={submitting}
            style={{ ...styles.actionBtn, background: '#27ae60', color: 'white' }}
          >
            Accept Decision
          </button>
          <button
            onClick={() => setActivePanel(activePanel === 'override' ? 'none' : 'override')}
            disabled={submitting}
            style={{
              ...styles.actionBtn,
              background: activePanel === 'override' ? '#c0392b' : '#e74c3c',
              color: 'white',
            }}
          >
            {activePanel === 'override' ? 'Cancel Override' : 'Override'}
          </button>
          <button
            onClick={() => setActivePanel(activePanel === 'feedback' ? 'none' : 'feedback')}
            disabled={submitting}
            style={{
              ...styles.actionBtn,
              background: activePanel === 'feedback' ? '#555' : '#7f8c8d',
              color: 'white',
            }}
          >
            {activePanel === 'feedback' ? 'Cancel Feedback' : 'Rate Explanation'}
          </button>
        </div>

        {activePanel === 'override' && (
          <div style={styles.subForm}>
            <div style={styles.auditNotice}>
              This override will be logged in the audit trail. The original decision is preserved.
            </div>
            <div style={{ display: 'flex', gap: 12, marginBottom: 10, flexWrap: 'wrap' }}>
              <div style={{ flex: 1, minWidth: 140 }}>
                <label style={styles.label}>New Priority *</label>
                <select
                  style={styles.input}
                  value={overridePriority}
                  onChange={(e) => setOverridePriority(e.target.value as Priority)}
                >
                  {PRIORITIES.map((p) => (
                    <option key={p} value={p}>{p}</option>
                  ))}
                </select>
              </div>
              <div style={{ flex: 2, minWidth: 200 }}>
                <label style={styles.label}>New Route (optional)</label>
                <input
                  style={styles.input}
                  value={overrideRoute}
                  onChange={(e) => setOverrideRoute(e.target.value)}
                  placeholder={`Current: ${result.final_route}`}
                />
              </div>
            </div>
            <div style={{ marginBottom: 10 }}>
              <label style={styles.label}>Clinical Reason * (required for audit)</label>
              <textarea
                style={{ ...styles.input, minHeight: 60, resize: 'vertical', width: '100%', boxSizing: 'border-box' }}
                value={overrideReason}
                onChange={(e) => setOverrideReason(e.target.value)}
                placeholder="Describe the clinical context that justifies this override..."
              />
            </div>
            <button
              onClick={handleOverrideSubmit}
              disabled={submitting}
              style={{ ...styles.actionBtn, background: '#c0392b', color: 'white' }}
            >
              {submitting ? 'Submitting...' : 'Confirm Override'}
            </button>
          </div>
        )}

        {activePanel === 'feedback' && (
          <div style={styles.subForm}>
            <div style={{ marginBottom: 10 }}>
              <label style={styles.label}>Was this explanation helpful?</label>
              <div style={{ display: 'flex', gap: 8 }}>
                <button
                  onClick={() => setFeedbackRating('helpful')}
                  style={{
                    ...styles.actionBtn,
                    background: feedbackRating === 'helpful' ? '#27ae60' : '#eee',
                    color: feedbackRating === 'helpful' ? 'white' : '#333',
                    border: '1px solid #ccc',
                  }}
                >
                  Helpful
                </button>
                <button
                  onClick={() => setFeedbackRating('not_helpful')}
                  style={{
                    ...styles.actionBtn,
                    background: feedbackRating === 'not_helpful' ? '#e74c3c' : '#eee',
                    color: feedbackRating === 'not_helpful' ? 'white' : '#333',
                    border: '1px solid #ccc',
                  }}
                >
                  Not Helpful
                </button>
              </div>
            </div>
            {feedbackRating === 'not_helpful' && (
              <div style={{ marginBottom: 10 }}>
                <label style={styles.label}>Reason category</label>
                <select
                  style={styles.input}
                  value={feedbackCategory}
                  onChange={(e) => setFeedbackCategory(e.target.value)}
                >
                  <option value="">- select -</option>
                  {FEEDBACK_REASON_CATEGORIES.map((c) => (
                    <option key={c} value={c}>{c.replace(/_/g, ' ')}</option>
                  ))}
                </select>
              </div>
            )}
            <div style={{ marginBottom: 10 }}>
              <label style={styles.label}>Comment (optional)</label>
              <textarea
                style={{ ...styles.input, minHeight: 52, resize: 'vertical', width: '100%', boxSizing: 'border-box' }}
                value={feedbackComment}
                onChange={(e) => setFeedbackComment(e.target.value)}
                placeholder="Any additional notes on explanation quality..."
              />
            </div>
            <button
              onClick={handleFeedbackSubmit}
              disabled={submitting || !feedbackRating}
              style={{ ...styles.actionBtn, background: '#2980b9', color: 'white' }}
            >
              {submitting ? 'Submitting...' : 'Submit Feedback'}
            </button>
          </div>
        )}

        {error && (
          <div style={{ marginTop: 10, color: '#c0392b', fontSize: 12, padding: '6px 10px', background: '#fdf2f2', borderRadius: 4 }}>
            {error}
          </div>
        )}
        {successMsg && (
          <div style={{ marginTop: 10, color: '#27ae60', fontSize: 12, padding: '6px 10px', background: '#f0faf4', borderRadius: 4 }}>
            {successMsg}
          </div>
        )}
      </div>
    </div>
  )
}

const styles = {
  sectionTitle: {
    margin: '0 0 8px',
    fontSize: 13,
    textTransform: 'uppercase' as const,
    color: '#555',
    letterSpacing: 1,
  },
  label: {
    display: 'block' as const,
    fontSize: 12,
    color: '#555',
    marginBottom: 4,
    fontWeight: 500,
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
  actionBtn: {
    padding: '7px 14px',
    border: 'none',
    borderRadius: 5,
    cursor: 'pointer',
    fontSize: 13,
    fontWeight: 500,
  },
  subForm: {
    borderTop: '1px solid #eee',
    paddingTop: 12,
    marginTop: 4,
  },
  auditNotice: {
    fontSize: 12,
    color: '#856404',
    background: '#fff8e1',
    border: '1px solid #ffe082',
    borderRadius: 4,
    padding: '6px 10px',
    marginBottom: 12,
  },
  overrideBadge: {
    fontSize: 12,
    color: '#5d4037',
    background: '#fff3e0',
    border: '1px solid #ffcc80',
    borderRadius: 4,
    padding: '6px 10px',
    marginBottom: 10,
  },
  acceptedBadge: {
    fontSize: 12,
    color: '#1b5e20',
    background: '#f0faf4',
    border: '1px solid #a5d6a7',
    borderRadius: 4,
    padding: '6px 10px',
    marginBottom: 10,
  },
}
