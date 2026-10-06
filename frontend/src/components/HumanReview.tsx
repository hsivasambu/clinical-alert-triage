import { ReviewHistory } from './ReviewHistory'
import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import type {
  AcceptanceRecord,
  AlertAudit,
  FeedbackRating,
  OverrideRecord,
  Priority,
  TriageResult,
} from '../types'
import { About } from './Callouts'
import { FEEDBACK_REASON_CATEGORIES, PRIORITIES } from '../types'

interface Props {
  result: TriageResult
  audit: AlertAudit | null
  reviewerId: string
  onReviewerIdChange: (id: string) => void
  onAuditUpdate: (audit: AlertAudit) => void
}

type Panel = 'none' | 'override' | 'feedback'

export function HumanReview({ result, audit, reviewerId, onReviewerIdChange, onAuditUpdate }: Props) {
  const mounted = useRef(true)
  useEffect(() => {
    mounted.current = true
    return () => { mounted.current = false }
  }, [])
  const state = audit?.review_state ?? result.review_state
  const [historyError, setHistoryError] = useState<string | null>(null)
  const [activePanel, setActivePanel] = useState<Panel>('none')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  const [overridePriority, setOverridePriority] = useState<Priority>(state?.effective_priority ?? result.final_priority)
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
    if (mounted.current) setHistoryError(null)
  }

  async function refreshAfterSave() {
    try { await refreshAudit() }
    catch { if (mounted.current) setHistoryError('Action saved. History refresh failed; retry loading history, do not resubmit the action.') }
  }

  useEffect(() => {
    refreshAudit().catch(() => {
      if (mounted.current) setHistoryError('Review history could not be loaded. Retry before reviewing.')
    })
  }, [])

  function showSuccess(msg: string) {
    setSuccessMsg(msg)
    setError(null)
  }

  async function handleAccept() {
    if (!reviewerId.trim()) {
      setError('Reviewer ID is required.')
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      const record = await api.acceptAlert(result.alert_id, reviewerId, state?.decision_version)
      if (audit && record.review_state) onAuditUpdate({ ...audit, acceptances: [...audit.acceptances, record], review_state: record.review_state })
      if (mounted.current) showSuccess('Decision accepted and logged.')
      await refreshAfterSave()
    } catch (e) {
      if (mounted.current) setError(e instanceof Error ? e.message : 'Accept failed.')
    } finally {
      if (mounted.current) setSubmitting(false)
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
      const record = await api.submitOverride(result.alert_id, {
        reviewer_id: reviewerId,
        overridden_priority: overridePriority,
        overridden_route: overrideRoute.trim() || undefined,
        reason: overrideReason,
      })
      if (audit && record.review_state) onAuditUpdate({ ...audit, overrides: [...audit.overrides, record], review_state: record.review_state })
      if (mounted.current) {
        setActivePanel('none')
        setOverrideReason('')
        showSuccess('Override recorded in audit log.')
      }
      await refreshAfterSave()
    } catch (e) {
      if (mounted.current) setError(e instanceof Error ? e.message : 'Override failed.')
    } finally {
      if (mounted.current) setSubmitting(false)
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
      const record = await api.submitFeedback(result.alert_id, {
        reviewer_id: reviewerId,
        rating: feedbackRating,
        reason_category: feedbackCategory || undefined,
        comment: feedbackComment.trim() || undefined,
      })
      if (audit) onAuditUpdate({ ...audit, feedback: [...audit.feedback, record] })
      if (!mounted.current) return
      setActivePanel('none')
      setFeedbackRating(null)
      setFeedbackCategory('')
      setFeedbackComment('')
      showSuccess('Feedback recorded. Thank you.')
      await refreshAfterSave()
    } catch (e) {
      if (mounted.current) setError(e instanceof Error ? e.message : 'Feedback submission failed.')
    } finally {
      if (mounted.current) setSubmitting(false)
    }
  }

  return (
    <section id="human-review" className="panel human-review" tabIndex={-1} aria-labelledby="review-heading">
      <h3 id="review-heading">Human Review</h3>
      <About>Accept the current decision, record a human override, or rate the explanation. Each action is logged.</About>
      {!audit && !historyError && <p role="status">Loading review history…</p>}
      <div>
        {latestOverride && (
          <div>
            <strong>Overridden</strong> by {latestOverride.reviewer_id} -
            {' '}
            <span>
              {latestOverride.original_priority}
            </span>
            {' -> '}
            <span>
              {latestOverride.overridden_priority}
            </span>
            <div>
              Reason: {latestOverride.reason}
            </div>
          </div>
        )}
        {latestAcceptance && state?.review_status === 'accepted' && (
          <div>
            Accepted by {latestAcceptance.reviewer_id} at{' '}
            {new Date(latestAcceptance.created_at).toLocaleTimeString()}
          </div>
        )}
        {hasFeedback && (
          <div>
            Feedback recorded ({audit!.feedback.length} submission{audit!.feedback.length !== 1 ? 's' : ''})
          </div>
        )}

        <div>
          <label className="form-label" htmlFor="reviewer-id">Reviewer ID</label>
          <input className="form-input" id="reviewer-id" required
            value={reviewerId}
            onChange={(e) => { onReviewerIdChange(e.target.value); setError(null) }}
            placeholder="e.g. Dr. Smith"
          />
        </div>

        <div>
          <button className="button button-primary"
            onClick={handleAccept}
            disabled={submitting || !audit}
          >
            Accept Decision
          </button>
          <button className="button"
            aria-expanded={activePanel === 'override'} aria-controls="override-form" onClick={() => { setOverridePriority(state?.effective_priority ?? result.final_priority); setOverrideRoute(''); setActivePanel(activePanel === 'override' ? 'none' : 'override') }}
            disabled={submitting || !audit}
          >
            {activePanel === 'override' ? 'Cancel Override' : 'Override'}
          </button>
          <button className="button"
            aria-expanded={activePanel === 'feedback'} aria-controls="feedback-form" onClick={() => setActivePanel(activePanel === 'feedback' ? 'none' : 'feedback')}
            disabled={submitting || !audit}
          >
            {activePanel === 'feedback' ? 'Cancel Feedback' : 'Rate Explanation'}
          </button>
        </div>

        {activePanel === 'override' && (
          <div id="override-form" className="review-form">
            <div>
              This override will be logged in the audit trail. The original decision is preserved.
            </div>
            <div>
              <div>
                <label className="form-label" htmlFor="override-priority">New Priority *</label>
                <select className="form-input" id="override-priority"
                  value={overridePriority}
                  onChange={(e) => setOverridePriority(e.target.value as Priority)}
                >
                  {PRIORITIES.map((p) => (
                    <option key={p} value={p}>{p}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="form-label" htmlFor="override-route">New Route (optional)</label>
                <input className="form-input" id="override-route"
                  value={overrideRoute}
                  onChange={(e) => setOverrideRoute(e.target.value)}
                  placeholder={`Current: ${state?.effective_route ?? result.final_route}`}
                />
              </div>
            </div>
            <div>
              <label className="form-label" htmlFor="override-reason">Clinical Reason * (required for audit)</label>
              <textarea className="form-input" id="override-reason" required
                value={overrideReason}
                onChange={(e) => setOverrideReason(e.target.value)}
                placeholder="Describe the clinical context that justifies this override..."
              />
            </div>
            <button className="button"
              onClick={handleOverrideSubmit}
              disabled={submitting || !audit}
            >
              {submitting ? 'Submitting...' : 'Confirm Override'}
            </button>
          </div>
        )}

        {activePanel === 'feedback' && (
          <div id="feedback-form" className="review-form">
            <div>
              <p className="form-label">Was this explanation helpful?</p>
              <div>
                <button className="button"
                  aria-pressed={feedbackRating === 'helpful'} onClick={() => setFeedbackRating('helpful')}
                >
                  Helpful
                </button>
                <button className="button"
                  aria-pressed={feedbackRating === 'not_helpful'} onClick={() => setFeedbackRating('not_helpful')}
                >
                  Not Helpful
                </button>
              </div>
            </div>
            {feedbackRating === 'not_helpful' && (
              <div>
                <label className="form-label" htmlFor="feedback-category">Reason category</label>
                <select className="form-input" id="feedback-category" required
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
            <div>
              <label className="form-label" htmlFor="feedback-comment">Comment (optional)</label>
              <textarea className="form-input" id="feedback-comment"
                value={feedbackComment}
                onChange={(e) => setFeedbackComment(e.target.value)}
                placeholder="Any additional notes on explanation quality..."
              />
            </div>
            <button className="button"
              onClick={handleFeedbackSubmit}
              disabled={submitting || !feedbackRating}
            >
              {submitting ? 'Submitting...' : 'Submit Feedback'}
            </button>
          </div>
        )}

        <div>
          Review status: {state?.review_status ?? 'unreviewed'}; decision version: {state?.decision_version ?? 0}
          <div>History: {audit?.overrides.length ?? 0} overrides, {audit?.acceptances.length ?? 0} acceptances</div>
          {audit && <details><summary>Review history</summary>
            <ReviewHistory audit={audit} />
          </details>}
        </div>
        {historyError && <div role="alert" className="notice notice-error">{historyError} <button className="button" onClick={() => refreshAudit().catch(() => setHistoryError('History refresh failed. Retry loading history.'))}>Retry history</button></div>}
        {error && (
          <div className="notice notice-error" role="alert">
            {error}
          </div>
        )}
        {successMsg && (
          <div className="notice notice-success" role="status">
            {successMsg}
          </div>
        )}
      </div>
    </section>
  )
}
