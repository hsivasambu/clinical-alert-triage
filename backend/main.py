"""
FastAPI entry point — Clinical Alert Triage API.

Run from the backend/ directory:
    uvicorn main:app --reload

Endpoints:
    POST /alerts                    Triage a new alert
    GET  /alerts                    List all triage results (newest first)
    GET  /alerts/{id}               Retrieve a single triage result
    POST /alerts/{id}/accept        Record clinician acceptance
    POST /alerts/{id}/override      Record clinician priority/route override
    POST /alerts/{id}/feedback      Record explanation quality feedback
    GET  /alerts/{id}/audit         Full audit record for one alert
    GET  /audit                     Audit log with filters (newest first)
    GET  /health                    Health check

LLM explainability is active when OPENAI_API_KEY is set in the environment.
Without it the system runs in rules_only mode — all endpoints remain functional.

Safety contract (enforced in decision_layer.py):
  - Rules define the minimum severity floor; LLM cannot downgrade critical alerts.
  - Overrides are appended to a separate audit table; the original triage record
    is never mutated.
"""

from __future__ import annotations

import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)

import database
import decision_layer
import llm_explainer
import rules_engine
from models import (
    AcceptanceIn,
    AcceptanceRecord,
    AlertIn,
    FeedbackIn,
    FeedbackRecord,
    FEEDBACK_REASON_CATEGORIES,
    OverrideIn,
    OverrideRecord,
    TriageResult,
)


_SEED_FILES = [
    "alerts_tachycardia.json",
    "alerts_low_spo2.json",
    "alerts_infusion_pump.json",
    "alerts_nurse_call.json",
    "alerts_fall_risk.json",
    "alerts_sepsis.json",
]

_SAMPLE_DIR = Path(__file__).parent.parent / "sample_data"


def _seed_sample_data() -> None:
    """Populate the store with sample alerts when the database is empty."""
    for filename in _SEED_FILES:
        path = _SAMPLE_DIR / filename
        if not path.exists():
            continue
        try:
            alert = AlertIn(**json.loads(path.read_text()))
            if alert.alert_id in _store:
                continue
            rule_output = rules_engine.evaluate(alert)
            llm_output = llm_explainer.explain(alert, rule_output)
            result = decision_layer.apply(alert, rule_output, llm_output=llm_output)
            _store[alert.alert_id] = result
            database.log_triage(alert, rule_output, result)
        except Exception as exc:
            logger.warning("Skipping seed file %s: %s", filename, exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    _store.clear()
    for result in database.load_triage_results():
        _store[result.alert_id] = result
    if not _store:
        _seed_sample_data()
    yield


app = FastAPI(
    title="Clinical Alert Triage API",
    description="Hybrid rules + LLM clinical alert triage — MVP",
    version="0.3.0",
    lifespan=lifespan,
)

_cors_origins = ["http://localhost:5173"]
_extra = os.environ.get("ALLOWED_ORIGINS", "")
if _extra:
    _cors_origins.extend(o.strip() for o in _extra.split(",") if o.strip())

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store — every triage result is also persisted to SQLite via database.py
_store: Dict[str, TriageResult] = {}


# ---------------------------------------------------------------------------
# Alert endpoints
# ---------------------------------------------------------------------------

@app.post("/alerts", response_model=TriageResult, status_code=201)
def triage_alert(alert: AlertIn) -> TriageResult:
    """
    Ingest a new alert, run the rules engine, apply guardrails, persist to
    the audit log, and return the full triage result.

    Returns 409 if alert_id has already been processed.
    """
    if alert.alert_id in _store:
        raise HTTPException(
            status_code=409,
            detail=f"Alert '{alert.alert_id}' has already been processed.",
        )

    rule_output = rules_engine.evaluate(alert)
    llm_output = llm_explainer.explain(alert, rule_output)
    result = decision_layer.apply(alert, rule_output, llm_output=llm_output)

    _store[alert.alert_id] = result
    database.log_triage(alert, rule_output, result)
    return result


@app.get("/alerts", response_model=List[TriageResult])
def list_alerts() -> List[TriageResult]:
    """Return all in-memory triage results, newest first."""
    return sorted(_store.values(), key=lambda r: r.processed_at, reverse=True)


@app.get("/alerts/{alert_id}", response_model=TriageResult)
def get_alert(alert_id: str) -> TriageResult:
    """Return a single triage result by alert_id."""
    result = _store.get(alert_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found.")
    return result


# ---------------------------------------------------------------------------
# Human review endpoints
# ---------------------------------------------------------------------------

@app.post("/alerts/{alert_id}/accept", response_model=AcceptanceRecord, status_code=201)
def accept_alert(alert_id: str, body: AcceptanceIn) -> AcceptanceRecord:
    """
    Record that a clinician reviewed and accepted the triage decision.
    Does not modify the original triage record.
    """
    if alert_id not in _store:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found.")
    return database.log_acceptance(alert_id, body)


@app.post("/alerts/{alert_id}/override", response_model=OverrideRecord, status_code=201)
def override_alert(alert_id: str, body: OverrideIn) -> OverrideRecord:
    """
    Record a clinician override of priority and/or route.
    The original triage record is preserved unchanged; the override is appended
    to a separate audit table for full traceability.
    """
    result = _store.get(alert_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found.")

    return database.log_override(
        alert_id=alert_id,
        override_in=body,
        original_priority=result.final_priority,
        original_route=result.final_route,
    )


@app.post("/alerts/{alert_id}/feedback", response_model=FeedbackRecord, status_code=201)
def submit_feedback(alert_id: str, body: FeedbackIn) -> FeedbackRecord:
    """
    Record explanation quality feedback from a clinician.
    Multiple feedback submissions per alert are allowed (each is appended).
    """
    if alert_id not in _store:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found.")
    return database.log_feedback(alert_id, body)


@app.get("/alerts/{alert_id}/audit")
def get_alert_audit(alert_id: str) -> dict:
    """
    Return the full audit record for one alert: triage result + all human actions
    (overrides, feedback, acceptances) in submission order.
    """
    result = _store.get(alert_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found.")
    return database.get_alert_audit(alert_id, result)


# ---------------------------------------------------------------------------
# Audit log endpoint
# ---------------------------------------------------------------------------

@app.get("/audit")
def get_audit(
    limit: int = Query(100, ge=1, le=1000),
    alert_type: Optional[str] = Query(None),
    final_priority: Optional[str] = Query(None),
    explanation_mode: Optional[str] = Query(None),
    overridden_only: bool = Query(False),
) -> List[dict]:
    """
    Return audit log entries (newest first) with optional filters.
    Each entry includes override_count, feedback_count, acceptance_count.
    JSON blobs (alert_json, etc.) are excluded from this list view for brevity.
    Use GET /alerts/{id}/audit for the full record of a single alert.
    """
    return database.get_audit_log(
        limit=limit,
        alert_type=alert_type,
        final_priority=final_priority,
        explanation_mode=explanation_mode,
        overridden_only=overridden_only,
    )


# ---------------------------------------------------------------------------
# Metadata endpoint
# ---------------------------------------------------------------------------

@app.get("/meta/feedback-categories")
def feedback_categories() -> List[str]:
    """Return the allowed feedback reason categories."""
    return FEEDBACK_REASON_CATEGORIES


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}
