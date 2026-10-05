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

LLM explainability is active when OPENAI_API_KEY is set and LLM_ENABLED is not false.
Without it the system runs in rules_only mode. Startup fixtures always run offline.

Safety contract (enforced in decision_layer.py):
  - Rules define the minimum severity floor; LLM cannot downgrade critical alerts.
  - Overrides are appended to a separate audit table; the original triage record
    is never mutated.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sqlite3
from threading import Lock, Event
from uuid import uuid4
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

import database
from demo_limits import DemoLimits, DemoLimitMiddleware
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


_initialization = {"state": "ready", "seed_failures": 0}
_store_lock = Lock()
_inflight: set[str] = set()
_seed_stop = Event()


def _persist_alert(alert: AlertIn, correlation: str | None = None, *, allow_provider=True) -> TriageResult:
    with _store_lock:
        if alert.alert_id in _store or alert.alert_id in _inflight or database.has_alert(alert.alert_id):
            raise database.DuplicateAlertError(alert.alert_id)
        database.check_alert_capacity()
        _inflight.add(alert.alert_id)
    try:
        rules = rules_engine.evaluate(alert)
        outcome = llm_explainer.explain_with_outcome(alert, rules, correlation, allow_provider=allow_provider)
        result = decision_layer.apply(alert, rules, outcome)
        database.log_triage(alert, rules, result)  # Commit before publishing to memory.
        with _store_lock: _store[alert.alert_id] = result
        return result
    finally:
        with _store_lock: _inflight.discard(alert.alert_id)


def _seed_sample_data() -> int:
    """Deterministic offline fixtures; provider latency cannot delay startup."""
    failures = 0
    for filename in _SEED_FILES:
        if _seed_stop.is_set(): break
        try:
            alert = AlertIn.model_validate_json((_SAMPLE_DIR / filename).read_text(encoding="utf-8"))
            _persist_alert(alert, allow_provider=False)
        except database.DuplicateAlertError:
            pass
        except Exception:
            failures += 1
            logger.exception("Could not persist seed fixture %s", filename)
    return failures


async def _initialize_samples():
    try:
        failures = await asyncio.to_thread(_seed_sample_data)
        _initialization.update(state="unavailable" if failures and not _store else "ready", seed_failures=failures)
    except Exception:
        _initialization.update(state="unavailable", seed_failures=len(_SEED_FILES))
        logger.exception("Sample initialization failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = None
    _seed_stop.clear()
    _initialization.update(state="initializing", seed_failures=0)
    try:
        database.init_db()
        with _store_lock:
            _store.clear(); _inflight.clear()
            for result in database.load_triage_results(): _store[result.alert_id] = result
        if not _store and database.persisted_alert_count() > 0:
            _initialization["state"] = "unavailable"
            logger.error("Persisted audit rows exist but no usable decisions could be restored")
        elif not _store and os.environ.get("SEED_SAMPLE_DATA", "true").lower() not in {"false", "0", "no"}:
            task = asyncio.create_task(_initialize_samples())
        else: _initialization["state"] = "ready"
    except sqlite3.Error:
        _initialization["state"] = "unavailable"
        logger.exception("Demo storage initialization failed")
    try: yield
    finally:
        _seed_stop.set()
        if task:
            await task  # Offline seeding has no external provider wait.



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

demo_limits = DemoLimits()
app.add_middleware(DemoLimitMiddleware, limits=demo_limits)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Demo-State", "Retry-After"],
)

@app.middleware("http")
async def correlation_id(request: Request, call_next):
    supplied = request.headers.get("X-Request-ID", "")
    request.state.correlation_id = supplied if re.fullmatch(r"[A-Za-z0-9._-]{1,128}", supplied) else str(uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.correlation_id
    return response


# In-memory store — every triage result is also persisted to SQLite via database.py
_store: Dict[str, TriageResult] = {}


# ---------------------------------------------------------------------------
# Alert endpoints
# ---------------------------------------------------------------------------

@app.exception_handler(RequestValidationError)
async def validation_error_response(request, exc: RequestValidationError):
    # Avoid reflecting raw invalid inputs (including NaN/Infinity) or exception
    # objects into JSON. Location/type/message are sufficient for form feedback.
    return JSONResponse(status_code=422, content={"detail": [
        {"type": error["type"], "loc": error["loc"], "msg": error["msg"]}
        for error in exc.errors()
    ]})


@app.post("/alerts", response_model=TriageResult, status_code=201)
def triage_alert(alert: AlertIn, request: Request = None) -> TriageResult:
    """
    Ingest a new alert, run the rules engine, apply guardrails, persist to
    the audit log, and return the full triage result.

    Returns 409 if alert_id has already been processed.
    """
    if _initialization["state"] == "unavailable":
        raise HTTPException(503, "Demo storage is unavailable. Retry later.")
    try:
        return _persist_alert(alert, getattr(request.state, "correlation_id", None) if request else None)
    except database.DuplicateAlertError:
        raise HTTPException(409, f"Alert '{alert.alert_id}' has already been processed or is processing.") from None
    except database.DemoCapacityError as exc:
        raise HTTPException(503, str(exc)) from None
    except sqlite3.Error:
        logger.exception("Triage persistence failed")
        raise HTTPException(503, "Decision could not be saved to the audit database. No alert was published; retry with the same alert ID.") from None


@app.get("/alerts", response_model=List[TriageResult])
def list_alerts(response: Response = None) -> List[TriageResult]:
    """Return all in-memory triage results, newest first."""
    if response is not None: response.headers["X-Demo-State"] = _initialization["state"]
    if _initialization["state"] == "unavailable": raise HTTPException(503, "Demo initialization/storage unavailable.")
    with _store_lock: results = list(_store.values())
    return [with_review(r) for r in sorted(results, key=lambda r: (r.processed_at, r.alert_id), reverse=True)]


@app.get("/alerts/{alert_id}", response_model=TriageResult)
def get_alert(alert_id: str) -> TriageResult:
    """Return a single triage result by alert_id."""
    result = _store.get(alert_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found.")
    return with_review(result)


def with_review(result: TriageResult) -> TriageResult:
    return result.model_copy(update={"review_state": database.get_review_state(result.alert_id, result)})


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
    try:
        record = database.log_acceptance(alert_id, body, triage_result=_store[alert_id])
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return record.model_copy(update={"review_state": database.get_review_state(alert_id, _store[alert_id])})


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

    record = database.log_override(
        alert_id=alert_id,
        override_in=body,
        original_priority=result.final_priority,
        original_route=result.final_route,
    )
    return record.model_copy(update={"review_state": database.get_review_state(alert_id, result)})


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
#
# Liveness only: confirms the ASGI app is up and answering requests. No DB,
# LLM, or other dependency check — a readiness probe would be a separate
# endpoint. Starlette does not auto-add HEAD to a GET-only route (that's a
# Flask behavior, not Starlette's), so HEAD must be declared explicitly or
# monitors using HEAD get a 405.

@app.api_route("/health", methods=["GET", "HEAD"])
def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/ready")
def readiness(response: Response):
    if _initialization["state"] == "unavailable": response.status_code = 503
    elif _initialization["state"] == "initializing": response.status_code = 202
    return {**_initialization, "alert_count": len(_store)}


@app.exception_handler(sqlite3.Error)
async def storage_error(request, exc):
    logger.error("Demo storage operation failed", exc_info=exc)
    return JSONResponse(status_code=503, content={"detail": "Demo storage is unavailable. If this was a review action, reload its history before retrying; its commit status may be unknown."})


@app.exception_handler(database.DemoCapacityError)
async def capacity_error(request, exc):
    return JSONResponse(status_code=503, content={"detail": str(exc)})
