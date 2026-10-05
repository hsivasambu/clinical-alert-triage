"""
Tests for human review endpoints: accept, override, feedback, audit.

Uses FastAPI TestClient with a temp SQLite database so the real audit.db is
never touched.  The in-memory _store in main.py is reset between test classes
via the clear_store fixture.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from fastapi.testclient import TestClient

import database
import main
from models import AlertType, VitalSigns
from tests.conftest import make_alert


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    """
    Redirect all database calls to a fresh temp DB for each test.
    database functions use late binding (_db() helper), so monkeypatching
    database.DB_PATH at the module level takes effect at call time.
    """
    db = tmp_path / "test_audit.db"
    monkeypatch.setattr(database, "DB_PATH", db)
    database.init_db()   # uses the monkeypatched DB_PATH
    yield db


@pytest.fixture(autouse=True)
def clear_store():
    """Clear the in-memory store before each test."""
    main._store.clear()
    yield
    main._store.clear()


@pytest.fixture
def client():
    return TestClient(main.app)


def post_alert(client: TestClient, alert_id: str = "TEST-001", alert_type: AlertType = AlertType.tachycardia):
    alert = make_alert(alert_id=alert_id, alert_type=alert_type,
                       vital_signs=VitalSigns(heart_rate=138))
    resp = client.post("/alerts", json=alert.model_dump(mode="json"))
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Accept
# ---------------------------------------------------------------------------

class TestAccept:
    def test_accept_returns_201(self, client):
        post_alert(client)
        resp = client.post("/alerts/TEST-001/accept", json={"reviewer_id": "Dr.Smith"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["alert_id"] == "TEST-001"
        assert data["reviewer_id"] == "Dr.Smith"
        assert "created_at" in data

    def test_accept_unknown_alert_returns_404(self, client):
        resp = client.post("/alerts/UNKNOWN/accept", json={"reviewer_id": "Dr.Smith"})
        assert resp.status_code == 404

    def test_accept_missing_reviewer_id_returns_422(self, client):
        post_alert(client)
        resp = client.post("/alerts/TEST-001/accept", json={})
        assert resp.status_code == 422

    def test_multiple_acceptances_allowed(self, client):
        post_alert(client)
        client.post("/alerts/TEST-001/accept", json={"reviewer_id": "Dr.A"})
        resp = client.post("/alerts/TEST-001/accept", json={"reviewer_id": "Dr.B"})
        assert resp.status_code == 201


# ---------------------------------------------------------------------------
# Override
# ---------------------------------------------------------------------------

class TestOverride:
    def test_override_returns_201_with_original_values(self, client):
        triage = post_alert(client)
        original_priority = triage["final_priority"]

        resp = client.post("/alerts/TEST-001/override", json={
            "reviewer_id": "Dr.Smith",
            "overridden_priority": "High",
            "reason": "Clinical context not captured by rules",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["alert_id"] == "TEST-001"
        assert data["original_priority"] == original_priority
        assert data["overridden_priority"] == "High"
        assert data["reason"] == "Clinical context not captured by rules"

    def test_override_with_route(self, client):
        post_alert(client)
        resp = client.post("/alerts/TEST-001/override", json={
            "reviewer_id": "Dr.Smith",
            "overridden_priority": "Critical",
            "overridden_route": "ICU Team (Intensivist + Nurse)",
            "reason": "Patient deteriorating rapidly",
        })
        assert resp.status_code == 201
        assert resp.json()["overridden_route"] == "ICU Team (Intensivist + Nurse)"

    def test_override_unknown_alert_returns_404(self, client):
        resp = client.post("/alerts/UNKNOWN/override", json={
            "reviewer_id": "Dr.Smith",
            "overridden_priority": "High",
            "reason": "Test",
        })
        assert resp.status_code == 404

    def test_override_missing_reason_returns_422(self, client):
        post_alert(client)
        resp = client.post("/alerts/TEST-001/override", json={
            "reviewer_id": "Dr.Smith",
            "overridden_priority": "High",
        })
        assert resp.status_code == 422

    def test_override_empty_reason_returns_422(self, client):
        post_alert(client)
        resp = client.post("/alerts/TEST-001/override", json={
            "reviewer_id": "Dr.Smith",
            "overridden_priority": "High",
            "reason": "",
        })
        assert resp.status_code == 422

    def test_original_triage_record_unchanged_after_override(self, client):
        triage = post_alert(client)
        original_priority = triage["final_priority"]

        client.post("/alerts/TEST-001/override", json={
            "reviewer_id": "Dr.Smith",
            "overridden_priority": "Low",
            "reason": "False positive",
        })

        # Original triage result must not be mutated
        get_resp = client.get("/alerts/TEST-001")
        assert get_resp.json()["final_priority"] == original_priority

    def test_multiple_overrides_allowed(self, client):
        post_alert(client)
        client.post("/alerts/TEST-001/override", json={
            "reviewer_id": "Dr.A", "overridden_priority": "High", "reason": "First override"
        })
        resp = client.post("/alerts/TEST-001/override", json={
            "reviewer_id": "Dr.B", "overridden_priority": "Critical", "reason": "Escalating"
        })
        assert resp.status_code == 201


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------

class TestFeedback:
    def test_feedback_helpful_returns_201(self, client):
        post_alert(client)
        resp = client.post("/alerts/TEST-001/feedback", json={
            "reviewer_id": "Dr.Smith",
            "rating": "helpful",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["rating"] == "helpful"
        assert data["alert_id"] == "TEST-001"

    def test_feedback_not_helpful_with_category(self, client):
        post_alert(client)
        resp = client.post("/alerts/TEST-001/feedback", json={
            "reviewer_id": "Dr.Smith",
            "rating": "not_helpful",
            "reason_category": "explanation_unclear",
            "comment": "Rationale was too vague",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["rating"] == "not_helpful"
        assert data["reason_category"] == "explanation_unclear"
        assert data["comment"] == "Rationale was too vague"

    def test_feedback_invalid_rating_returns_422(self, client):
        post_alert(client)
        resp = client.post("/alerts/TEST-001/feedback", json={
            "reviewer_id": "Dr.Smith",
            "rating": "maybe",
        })
        assert resp.status_code == 422

    def test_not_helpful_feedback_requires_reason_category(self, client):
        post_alert(client)
        resp = client.post("/alerts/TEST-001/feedback", json={
            "reviewer_id": "Dr.Smith",
            "rating": "not_helpful",
        })
        assert resp.status_code == 422

    def test_feedback_invalid_reason_category_returns_422(self, client):
        post_alert(client)
        resp = client.post("/alerts/TEST-001/feedback", json={
            "reviewer_id": "Dr.Smith",
            "rating": "not_helpful",
            "reason_category": "wrong_bucket",
        })
        assert resp.status_code == 422

    def test_feedback_unknown_alert_returns_404(self, client):
        resp = client.post("/alerts/UNKNOWN/feedback", json={
            "reviewer_id": "Dr.Smith",
            "rating": "helpful",
        })
        assert resp.status_code == 404

    def test_multiple_feedback_allowed(self, client):
        post_alert(client)
        client.post("/alerts/TEST-001/feedback", json={"reviewer_id": "Dr.A", "rating": "helpful"})
        resp = client.post("/alerts/TEST-001/feedback", json={"reviewer_id": "Dr.B", "rating": "not_helpful", "reason_category": "explanation_unclear"})
        assert resp.status_code == 201


# ---------------------------------------------------------------------------
# Alert audit endpoint
# ---------------------------------------------------------------------------

class TestAlertAudit:
    def test_audit_returns_triage_result(self, client):
        post_alert(client)
        resp = client.get("/alerts/TEST-001/audit")
        assert resp.status_code == 200
        data = resp.json()
        assert "triage_result" in data
        assert data["triage_result"]["alert_id"] == "TEST-001"

    def test_audit_includes_empty_lists_initially(self, client):
        post_alert(client)
        data = client.get("/alerts/TEST-001/audit").json()
        assert data["overrides"] == []
        assert data["feedback"] == []
        assert data["acceptances"] == []

    def test_audit_shows_all_actions(self, client):
        post_alert(client)
        client.post("/alerts/TEST-001/accept", json={"reviewer_id": "Dr.A"})
        client.post("/alerts/TEST-001/override", json={
            "reviewer_id": "Dr.B", "overridden_priority": "High", "reason": "Clinical judgement"
        })
        client.post("/alerts/TEST-001/feedback", json={"reviewer_id": "Dr.C", "rating": "helpful"})

        data = client.get("/alerts/TEST-001/audit").json()
        assert len(data["acceptances"]) == 1
        assert len(data["overrides"]) == 1
        assert len(data["feedback"]) == 1

    def test_audit_unknown_alert_returns_404(self, client):
        resp = client.get("/alerts/UNKNOWN/audit")
        assert resp.status_code == 404

    def test_audit_override_contains_original_values(self, client):
        triage = post_alert(client)
        original_priority = triage["final_priority"]

        client.post("/alerts/TEST-001/override", json={
            "reviewer_id": "Dr.B", "overridden_priority": "Low", "reason": "False positive"
        })
        data = client.get("/alerts/TEST-001/audit").json()
        override = data["overrides"][0]
        assert override["original_priority"] == original_priority
        assert override["overridden_priority"] == "Low"


# ---------------------------------------------------------------------------
# Audit log endpoint
# ---------------------------------------------------------------------------

class TestAuditLog:
    def test_audit_log_returns_entries(self, client):
        post_alert(client, "A-001")
        post_alert(client, "A-002")
        resp = client.get("/audit")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_audit_log_includes_counts(self, client):
        post_alert(client)
        client.post("/alerts/TEST-001/override", json={
            "reviewer_id": "Dr.A", "overridden_priority": "High", "reason": "Test"
        })
        client.post("/alerts/TEST-001/feedback", json={"reviewer_id": "Dr.B", "rating": "helpful"})

        entries = client.get("/audit").json()
        entry = next(e for e in entries if e["alert_id"] == "TEST-001")
        assert entry["override_count"] == 1
        assert entry["feedback_count"] == 1

    def test_audit_log_filter_by_alert_type(self, client):
        post_alert(client, "T-001", AlertType.tachycardia)
        post_alert(client, "S-001", AlertType.sepsis)

        resp = client.get("/audit?alert_type=sepsis")
        ids = [e["alert_id"] for e in resp.json()]
        assert "S-001" in ids
        assert "T-001" not in ids

    def test_audit_log_overridden_only_filter(self, client):
        post_alert(client, "A-001")
        post_alert(client, "A-002")
        client.post("/alerts/A-002/override", json={
            "reviewer_id": "Dr.A", "overridden_priority": "Low", "reason": "FP"
        })

        resp = client.get("/audit?overridden_only=true")
        ids = [e["alert_id"] for e in resp.json()]
        assert "A-002" in ids
        assert "A-001" not in ids


class TestEffectiveReview:
    def test_review_versions_route_retention_and_restart(self, client):
        original = post_alert(client)
        assert client.get('/alerts/TEST-001').json()['review_state']['review_status'] == 'unreviewed'
        accepted = client.post('/alerts/TEST-001/accept', json={'reviewer_id': 'A', 'decision_version': 0}).json()
        assert accepted['accepted_priority'] == original['final_priority']
        assert accepted['accepted_route'] == original['final_route']
        first = client.post('/alerts/TEST-001/override', json={
            'reviewer_id': 'B', 'overridden_priority': 'Low', 'overridden_route': 'Charge Nurse', 'reason': 'Demo review'
        }).json()
        assert first['review_state']['review_status'] == 'overridden'
        stale = client.post('/alerts/TEST-001/accept', json={'reviewer_id': 'A', 'decision_version': 0})
        assert stale.status_code == 409
        accepted = client.post('/alerts/TEST-001/accept', json={'reviewer_id': 'A', 'decision_version': first['id']}).json()
        assert accepted['accepted_priority'] == 'Low'
        assert accepted['accepted_route'] == 'Charge Nurse'
        assert accepted['review_state']['review_status'] == 'accepted'
        second = client.post('/alerts/TEST-001/override', json={
            'reviewer_id': 'C', 'overridden_priority': 'Medium', 'reason': 'Second review'
        }).json()
        assert second['review_state']['effective_route'] == 'Charge Nurse'
        assert second['review_state']['review_status'] == 'overridden'
        client.post('/alerts/TEST-001/feedback', json={'reviewer_id': 'A', 'rating': 'helpful'})
        main._store.clear()
        for result in database.load_triage_results():
            main._store[result.alert_id] = result
        detail = client.get('/alerts/TEST-001').json()
        assert detail['final_priority'] == original['final_priority']
        assert detail['final_route'] == original['final_route']
        assert detail['review_state'] == second['review_state']
        assert client.get('/alerts').json()[0]['review_state'] == second['review_state']
        audit = client.get('/alerts/TEST-001/audit').json()
        assert len(audit['overrides']) == 2
        assert len(audit['acceptances']) == 2
        assert len(audit['feedback']) == 1
        assert audit['acceptances'][0]['decision_version'] == 0
        assert audit['acceptances'][1]['decision_version'] == first['id']

    def test_legacy_acceptance_is_not_assumed_to_accept_current_version(self, client):
        post_alert(client)
        import sqlite3
        with sqlite3.connect(database.DB_PATH) as conn:
            conn.execute("INSERT INTO acceptances (alert_id, reviewer_id, created_at) VALUES (?, ?, ?)",
                         ('TEST-001', 'Legacy', '2024-01-01T00:00:00Z'))
        audit = client.get('/alerts/TEST-001/audit').json()
        assert audit['acceptances'][0]['decision_version'] is None
        assert audit['review_state']['review_status'] == 'unreviewed'


    def test_existing_database_migration_preserves_legacy_rows(self, tmp_path):
        import sqlite3
        path = tmp_path / 'legacy.db'
        with sqlite3.connect(path) as conn:
            conn.execute('CREATE TABLE acceptances (id INTEGER PRIMARY KEY, alert_id TEXT NOT NULL, reviewer_id TEXT NOT NULL, created_at TEXT NOT NULL)')
            conn.execute("INSERT INTO acceptances VALUES (1, 'OLD', 'Reviewer', '2024-01-01T00:00:00Z')")
        database.init_db(path)
        database.init_db(path)
        records = database.get_acceptances('OLD', path)
        assert len(records) == 1
        assert records[0].reviewer_id == 'Reviewer'
        assert records[0].decision_version is None
