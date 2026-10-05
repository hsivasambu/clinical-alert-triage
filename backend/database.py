"""
Audit logging — SQLite persistence layer (Layer 5).

Every triage decision and human review action is appended to audit.db.
Tables are append-only: records are never updated or deleted.

Schema overview:
  audit_log   — one row per triage decision (original decision, immutable)
  overrides   — one row per clinician override (append-only)
  feedback    — one row per explanation quality rating (append-only)
  acceptances — one row per clinician acceptance (append-only)

To migrate to PostgreSQL: replace DB_PATH / sqlite3 with SQLAlchemy or asyncpg.
Public API stays the same.

Implementation note: all functions use late binding (db_path defaults to None,
resolved to DB_PATH inside the function body). This ensures that monkeypatching
database.DB_PATH in tests actually takes effect.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from models import (
    AcceptanceIn,
    AcceptanceRecord,
    AlertIn,
    FeedbackIn,
    FeedbackRecord,
    OverrideIn,
    OverrideRecord,
    Priority,
    RuleOutput,
    ReviewState,
    TriageResult,
)

DB_PATH = Path(__file__).parent / "audit.db"
logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_log (
    id                   INTEGER  PRIMARY KEY AUTOINCREMENT,
    alert_id             TEXT     NOT NULL,
    alert_type           TEXT     NOT NULL,
    patient_id           TEXT     NOT NULL,
    unit                 TEXT     NOT NULL,
    baseline_priority    TEXT     NOT NULL,
    final_priority       TEXT     NOT NULL,
    final_route          TEXT     NOT NULL,
    explanation_mode     TEXT     NOT NULL,
    rule_confidence      REAL     NOT NULL,
    alert_json           TEXT     NOT NULL,
    rule_output_json     TEXT     NOT NULL,
    final_response_json  TEXT     NOT NULL,
    created_at           TEXT     NOT NULL
);

CREATE TABLE IF NOT EXISTS review_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_id TEXT NOT NULL, action_type TEXT NOT NULL, record_id INTEGER NOT NULL,
    created_at TEXT NOT NULL, UNIQUE(action_type, record_id)
);

CREATE TABLE IF NOT EXISTS overrides (
    id                   INTEGER  PRIMARY KEY AUTOINCREMENT,
    alert_id             TEXT     NOT NULL,
    reviewer_id          TEXT     NOT NULL,
    original_priority    TEXT     NOT NULL,
    original_route       TEXT     NOT NULL,
    overridden_priority  TEXT     NOT NULL,
    overridden_route     TEXT,
    reason               TEXT     NOT NULL,
    created_at           TEXT     NOT NULL
);

CREATE TABLE IF NOT EXISTS feedback (
    id               INTEGER  PRIMARY KEY AUTOINCREMENT,
    alert_id         TEXT     NOT NULL,
    reviewer_id      TEXT     NOT NULL,
    rating           TEXT     NOT NULL,
    reason_category  TEXT,
    comment          TEXT,
    created_at       TEXT     NOT NULL
);

CREATE TABLE IF NOT EXISTS acceptances (
    id           INTEGER  PRIMARY KEY AUTOINCREMENT,
    alert_id     TEXT     NOT NULL,
    reviewer_id  TEXT     NOT NULL,
    created_at   TEXT     NOT NULL
);
"""


def _db(path: Optional[Path]) -> Path:
    """Resolve the active database path — enables monkeypatching in tests."""
    return path if path is not None else DB_PATH


def init_db(db_path: Optional[Path] = None) -> None:
    """Create all tables if they do not already exist."""
    with sqlite3.connect(_db(db_path)) as conn:
        conn.executescript(_SCHEMA)
        columns = {r[1] for r in conn.execute("PRAGMA table_info(acceptances)")}
        for name, kind in [("decision_version", "INTEGER"), ("accepted_priority", "TEXT"), ("accepted_route", "TEXT")]:
            if name not in columns:
                conn.execute(f"ALTER TABLE acceptances ADD COLUMN {name} {kind}")
        audit_columns = {r[1] for r in conn.execute("PRAGMA table_info(audit_log)")}
        if "fallback_reason" not in audit_columns:
            conn.execute("ALTER TABLE audit_log ADD COLUMN fallback_reason TEXT")
        if "provenance_json" not in audit_columns:
            conn.execute("ALTER TABLE audit_log ADD COLUMN provenance_json TEXT")
        conn.commit()


# ---------------------------------------------------------------------------
# Triage logging
# ---------------------------------------------------------------------------

def log_triage(
    alert: AlertIn,
    rule_output: RuleOutput,
    result: TriageResult,
    db_path: Optional[Path] = None,
) -> None:
    """Append one triage decision to the audit log."""
    with sqlite3.connect(_db(db_path)) as conn:
        conn.execute(
            """
            INSERT INTO audit_log (
                alert_id, alert_type, patient_id, unit,
                baseline_priority, final_priority, final_route, explanation_mode,
                rule_confidence, fallback_reason, provenance_json,
                alert_json, rule_output_json, final_response_json,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                alert.alert_id,
                alert.alert_type.value,
                alert.patient_id,
                alert.unit,
                rule_output.baseline_priority.value,
                result.final_priority.value,
                result.final_route,
                result.explanation.explanation_mode.value,
                rule_output.rule_confidence,
                result.explanation.fallback_reason,
                result.provenance.model_dump_json() if result.provenance else None,
                alert.model_dump_json(),
                rule_output.model_dump_json(),
                result.model_dump_json(),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()


def load_triage_results(db_path: Optional[Path] = None) -> List[TriageResult]:
    """
    Load persisted triage results from the audit log, newest first.

    The app uses this on startup to rebuild the in-memory alert store after a
    restart so GET /alerts continues to reflect persisted decisions.
    """
    with sqlite3.connect(_db(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT alert_id, final_response_json
            FROM audit_log
            ORDER BY created_at DESC, id DESC
            """
        ).fetchall()

    results: List[TriageResult] = []
    seen_alert_ids: set[str] = set()

    for row in rows:
        alert_id = row["alert_id"]
        if alert_id in seen_alert_ids:
            continue

        try:
            result = TriageResult.model_validate_json(row["final_response_json"])
        except Exception as exc:
            logger.warning("Skipping persisted triage row for alert_id=%s: %s", alert_id, exc)
            continue

        results.append(result)
        seen_alert_ids.add(alert_id)

    return results


# ---------------------------------------------------------------------------
# Override logging
# ---------------------------------------------------------------------------

def log_override(
    alert_id: str,
    override_in: OverrideIn,
    original_priority: Priority,
    original_route: str,
    db_path: Optional[Path] = None,
) -> OverrideRecord:
    """Append an override action and return the persisted record."""
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(_db(db_path)) as conn:
        cur = conn.execute(
            """
            INSERT INTO overrides (
                alert_id, reviewer_id,
                original_priority, original_route,
                overridden_priority, overridden_route,
                reason, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                alert_id,
                override_in.reviewer_id,
                original_priority.value,
                original_route,
                override_in.overridden_priority.value,
                override_in.overridden_route,
                override_in.reason,
                now,
            ),
        )
        row_id = cur.lastrowid
        event = conn.execute("INSERT INTO review_events (alert_id, action_type, record_id, created_at) VALUES (?, ?, ?, ?)",
                             (alert_id, "override", row_id, now))
        sequence = event.lastrowid
        conn.commit()

    return OverrideRecord(
        id=row_id,
        event_sequence=sequence,
        alert_id=alert_id,
        reviewer_id=override_in.reviewer_id,
        original_priority=original_priority,
        original_route=original_route,
        overridden_priority=override_in.overridden_priority,
        overridden_route=override_in.overridden_route,
        reason=override_in.reason,
        created_at=now,
    )


def get_overrides(alert_id: str, db_path: Optional[Path] = None) -> List[OverrideRecord]:
    """Return all overrides for an alert, oldest first."""
    with sqlite3.connect(_db(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT *, (SELECT sequence FROM review_events e WHERE e.action_type = 'override' AND e.record_id = overrides.id) AS event_sequence FROM overrides WHERE alert_id = ? ORDER BY id ASC",
            (alert_id,),
        ).fetchall()
    return [
        OverrideRecord(
            id=r["id"],
            event_sequence=r["event_sequence"],
            alert_id=r["alert_id"],
            reviewer_id=r["reviewer_id"],
            original_priority=r["original_priority"],
            original_route=r["original_route"],
            overridden_priority=r["overridden_priority"],
            overridden_route=r["overridden_route"],
            reason=r["reason"],
            created_at=r["created_at"],
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Feedback logging
# ---------------------------------------------------------------------------

def log_feedback(
    alert_id: str,
    feedback_in: FeedbackIn,
    db_path: Optional[Path] = None,
) -> FeedbackRecord:
    """Append explanation quality feedback and return the persisted record."""
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(_db(db_path)) as conn:
        cur = conn.execute(
            """
            INSERT INTO feedback (
                alert_id, reviewer_id, rating, reason_category, comment, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                alert_id,
                feedback_in.reviewer_id,
                feedback_in.rating,
                feedback_in.reason_category,
                feedback_in.comment,
                now,
            ),
        )
        row_id = cur.lastrowid
        event = conn.execute("INSERT INTO review_events (alert_id, action_type, record_id, created_at) VALUES (?, ?, ?, ?)",
                             (alert_id, "feedback", row_id, now))
        sequence = event.lastrowid
        conn.commit()

    return FeedbackRecord(
        id=row_id,
        event_sequence=sequence,
        alert_id=alert_id,
        reviewer_id=feedback_in.reviewer_id,
        rating=feedback_in.rating,
        reason_category=feedback_in.reason_category,
        comment=feedback_in.comment,
        created_at=now,
    )


def get_feedback(alert_id: str, db_path: Optional[Path] = None) -> List[FeedbackRecord]:
    """Return all feedback for an alert, oldest first."""
    with sqlite3.connect(_db(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT *, (SELECT sequence FROM review_events e WHERE e.action_type = 'feedback' AND e.record_id = feedback.id) AS event_sequence FROM feedback WHERE alert_id = ? ORDER BY id ASC",
            (alert_id,),
        ).fetchall()
    return [
        FeedbackRecord(
            id=r["id"],
            event_sequence=r["event_sequence"],
            alert_id=r["alert_id"],
            reviewer_id=r["reviewer_id"],
            rating=r["rating"],
            reason_category=r["reason_category"],
            comment=r["comment"],
            created_at=r["created_at"],
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Acceptance logging
# ---------------------------------------------------------------------------

def log_acceptance(
    alert_id: str,
    acceptance_in: AcceptanceIn,
    db_path: Optional[Path] = None,
    triage_result: Optional[TriageResult] = None,
) -> AcceptanceRecord:
    """Append an acceptance action and return the persisted record."""
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(_db(db_path)) as conn:
        conn.execute("BEGIN IMMEDIATE")
        state = get_review_state(alert_id, triage_result, db_path) if triage_result else None
        if state and acceptance_in.decision_version is not None and acceptance_in.decision_version != state.decision_version:
            raise ValueError("Decision changed; refresh before accepting.")
        cur = conn.execute(
            "INSERT INTO acceptances (alert_id, reviewer_id, created_at, decision_version, accepted_priority, accepted_route) VALUES (?, ?, ?, ?, ?, ?)",
            (alert_id, acceptance_in.reviewer_id, now, state.decision_version if state else None,
             state.effective_priority.value if state else None, state.effective_route if state else None),
        )
        row_id = cur.lastrowid
        event = conn.execute("INSERT INTO review_events (alert_id, action_type, record_id, created_at) VALUES (?, ?, ?, ?)",
                             (alert_id, "acceptance", row_id, now))
        sequence = event.lastrowid
        conn.commit()

    return AcceptanceRecord(
        id=row_id,
        event_sequence=sequence,
        alert_id=alert_id,
        reviewer_id=acceptance_in.reviewer_id,
        created_at=now,
        decision_version=state.decision_version if state else None,
        accepted_priority=state.effective_priority if state else None,
        accepted_route=state.effective_route if state else None,
    )


def get_acceptances(alert_id: str, db_path: Optional[Path] = None) -> List[AcceptanceRecord]:
    """Return all acceptances for an alert, oldest first."""
    with sqlite3.connect(_db(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT *, (SELECT sequence FROM review_events e WHERE e.action_type = 'acceptance' AND e.record_id = acceptances.id) AS event_sequence FROM acceptances WHERE alert_id = ? ORDER BY id ASC",
            (alert_id,),
        ).fetchall()
    return [
        AcceptanceRecord(
            id=r["id"],
            event_sequence=r["event_sequence"],
            alert_id=r["alert_id"],
            reviewer_id=r["reviewer_id"],
            created_at=r["created_at"],
            decision_version=r["decision_version"],
            accepted_priority=r["accepted_priority"],
            accepted_route=r["accepted_route"],
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Audit retrieval
# ---------------------------------------------------------------------------

def get_audit_log(
    limit: int = 100,
    alert_type: Optional[str] = None,
    final_priority: Optional[str] = None,
    explanation_mode: Optional[str] = None,
    overridden_only: bool = False,
    db_path: Optional[Path] = None,
) -> List[dict]:
    """
    Return audit log entries enriched with override/feedback/acceptance counts.
    Supports optional filters for alert_type, final_priority, explanation_mode,
    and overridden_only.
    """
    conditions = []
    params: list = []

    if alert_type:
        conditions.append("al.alert_type = ?")
        params.append(alert_type)
    if final_priority:
        conditions.append("al.final_priority = ?")
        params.append(final_priority)
    if explanation_mode:
        conditions.append("al.explanation_mode = ?")
        params.append(explanation_mode)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    having = "HAVING override_count > 0" if overridden_only else ""
    params.append(limit)

    query = f"""
        SELECT
            al.*,
            COUNT(DISTINCT o.id)  AS override_count,
            COUNT(DISTINCT f.id)  AS feedback_count,
            COUNT(DISTINCT ac.id) AS acceptance_count
        FROM audit_log al
        LEFT JOIN overrides   o  ON al.alert_id = o.alert_id
        LEFT JOIN feedback    f  ON al.alert_id = f.alert_id
        LEFT JOIN acceptances ac ON al.alert_id = ac.alert_id
        {where}
        GROUP BY al.id
        {having}
        ORDER BY al.created_at DESC
        LIMIT ?
    """
    with sqlite3.connect(_db(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, params).fetchall()

    results = []
    for row in rows:
        entry = dict(row)
        # Omit heavy JSON blobs from the list view
        entry.pop("alert_json", None)
        entry.pop("rule_output_json", None)
        entry.pop("final_response_json", None)
        entry["provenance"] = json.loads(entry.pop("provenance_json")) if entry.get("provenance_json") else None
        entry.pop("provenance_json", None)
        results.append(entry)
    return results


def get_alert_audit(alert_id: str, triage_result: TriageResult, db_path: Optional[Path] = None) -> dict:
    """
    Return the full audit record for one alert: triage result + all human actions.
    triage_result is passed in from the in-memory store to avoid re-parsing JSON.
    """
    overrides = get_overrides(alert_id, db_path)
    feedbacks = get_feedback(alert_id, db_path)
    acceptances = get_acceptances(alert_id, db_path)

    return {
        "triage_result": json.loads(triage_result.model_dump_json()),
        "review_state": get_review_state(alert_id, triage_result, db_path).model_dump(mode="json"),
        "overrides": [json.loads(r.model_dump_json()) for r in overrides],
        "feedback": [json.loads(r.model_dump_json()) for r in feedbacks],
        "acceptances": [json.loads(r.model_dump_json()) for r in acceptances],
    }


def get_review_state(alert_id: str, result: TriageResult, db_path: Optional[Path] = None) -> ReviewState:
    overrides = get_overrides(alert_id, db_path)
    priority, route, version = result.final_priority, result.final_route, 0
    for override in overrides:
        priority = override.overridden_priority
        route = override.overridden_route or route
        version = override.id
    accepted = any(a.decision_version == version and a.accepted_priority == priority and a.accepted_route == route
                   for a in get_acceptances(alert_id, db_path))
    return ReviewState(effective_priority=priority, effective_route=route, decision_version=version,
                       review_status="accepted" if accepted else "overridden" if version else "unreviewed")
