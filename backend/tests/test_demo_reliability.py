import asyncio
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import httpx
import pytest
from fastapi.testclient import TestClient

import database
import main
from demo_limits import DemoLimits, DemoLimitMiddleware
from models import AlertIn
from tests.conftest import make_alert

@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "demo.db")
    database.init_db(); main._store.clear(); main._inflight.clear()
    yield
    main._store.clear(); main._inflight.clear()


def test_failed_write_never_publishes_and_same_id_can_retry(isolated, monkeypatch):
    client = TestClient(main.app); alert = make_alert()
    original = database.log_triage
    monkeypatch.setattr(database, "log_triage", lambda *a, **k: (_ for _ in ()).throw(sqlite3.OperationalError("disk full")))
    response = client.post("/alerts", json=alert.model_dump(mode="json"))
    assert response.status_code == 503
    assert alert.alert_id not in main._store and alert.alert_id not in main._inflight
    assert not database.has_alert(alert.alert_id)
    assert client.get("/alerts").json() == []
    monkeypatch.setattr(database, "log_triage", original)
    assert client.post("/alerts", json=alert.model_dump(mode="json")).status_code == 201


def test_registry_rolls_back_if_audit_insert_fails(isolated):
    alert = make_alert(); rules = main.rules_engine.evaluate(alert); result = main.decision_layer.apply(alert, rules)
    with sqlite3.connect(database.DB_PATH) as conn:
        conn.execute("CREATE TRIGGER fail_audit BEFORE INSERT ON audit_log BEGIN SELECT RAISE(ABORT, 'simulated failure'); END")
    with pytest.raises(sqlite3.Error): database.log_triage(alert, rules, result)
    assert not database.has_alert(alert.alert_id)
    assert database.load_triage_results() == []


def test_concurrent_duplicate_is_rejected_before_second_explanation(isolated, monkeypatch):
    entered, release = Event(), Event(); calls = []
    original = main.llm_explainer.explain_with_outcome
    def blocked(*a, **k):
        calls.append(1); entered.set(); assert release.wait(5)
        return original(*a, **k)
    monkeypatch.setattr(main.llm_explainer, "explain_with_outcome", blocked)
    alert = make_alert()
    with ThreadPoolExecutor(2) as pool:
        first = pool.submit(main.triage_alert, alert)
        assert entered.wait(5)
        with pytest.raises(main.HTTPException) as error: main.triage_alert(alert)
        assert error.value.status_code == 409
        release.set(); first.result()
    assert len(calls) == 1
    with sqlite3.connect(database.DB_PATH) as conn: assert conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == 1


def test_restart_restores_review_and_duplicate_registry(isolated, monkeypatch):
    monkeypatch.setenv("SEED_SAMPLE_DATA", "false")
    alert = make_alert()
    with TestClient(main.app) as client:
        assert client.post("/alerts", json=alert.model_dump(mode="json")).status_code == 201
        override = client.post(f"/alerts/{alert.alert_id}/override", json={"reviewer_id": "offline", "overridden_priority": "High", "reason": "Synthetic review"}).json()
        assert client.post(f"/alerts/{alert.alert_id}/accept", json={"reviewer_id": "offline", "decision_version": override["id"]}).status_code == 201
    main._store.clear()
    with TestClient(main.app) as client:
        assert client.get("/ready").json()["state"] == "ready"
        assert client.get(f"/alerts/{alert.alert_id}").json()["review_state"]["review_status"] == "accepted"
        assert client.post("/alerts", json=alert.model_dump(mode="json")).status_code == 409


def test_initializing_empty_ready_and_failed_seeding_are_distinct(isolated, monkeypatch):
    client = TestClient(main.app)
    main._initialization["state"] = "initializing"
    assert client.get("/alerts").headers["X-Demo-State"] == "initializing"
    assert client.get("/ready").status_code == 202
    main._initialization["state"] = "ready"
    assert client.get("/alerts").json() == []
    assert client.get("/ready").json()["state"] == "ready"
    monkeypatch.setattr(main, "_seed_sample_data", lambda: 6)
    asyncio.run(main._initialize_samples())
    assert client.get("/alerts").status_code == client.get("/ready").status_code == 503


def test_seed_fixtures_never_call_provider(isolated, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "configured-but-not-used")
    main._seed_stop.clear()
    assert main._seed_sample_data() == 0
    assert len(main._store) == 6
    assert all(result.explanation.fallback_reason == "llm_disabled" for result in main._store.values())


def test_size_rate_and_storage_capacity(isolated, monkeypatch):
    client = TestClient(main.app)
    main.demo_limits.max_bytes = 100
    response = client.post("/alerts", content=b"x" * 101, headers={"Origin": "http://localhost:5173"})
    assert response.status_code == 413 and response.headers["X-Request-ID"]
    assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"
    main.demo_limits.max_bytes = 16384; main.demo_limits.per_client = 1
    assert client.post("/alerts", json=make_alert().model_dump(mode="json")).status_code == 429
    main.demo_limits.reset(); main.demo_limits.per_client = 20
    monkeypatch.setenv("DEMO_MAX_ALERTS", "1")
    assert client.post("/alerts", json=make_alert().model_dump(mode="json")).status_code == 201
    assert client.post("/alerts", json=make_alert(alert_id="OTHER").model_dump(mode="json")).status_code == 503
    assert "OTHER" not in main._store


@pytest.mark.asyncio
async def test_chunked_body_and_concurrency_limits_release_slots():
    limits = DemoLimits(); limits.max_bytes = 10; limits.max_concurrent = 1
    entered, release = asyncio.Event(), asyncio.Event()
    async def inner(scope, receive, send):
        await receive(); entered.set(); await release.wait()
        await main.JSONResponse({"ok": True})(scope, receive, send)
    app = DemoLimitMiddleware(inner, limits)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://offline") as client:
        async def oversized():
            yield b"123456"; yield b"789012"
        assert (await client.post("/alerts", content=oversized())).status_code == 413
        first = asyncio.create_task(client.post("/alerts", content=b"{}"))
        await entered.wait()
        assert (await client.post("/alerts", content=b"{}")).status_code == 429
        release.set(); assert (await first).status_code == 200
    assert limits.active == 0


def test_review_capacity_preserves_history_and_does_not_append(isolated, monkeypatch):
    client = TestClient(main.app); alert = make_alert()
    assert client.post("/alerts", json=alert.model_dump(mode="json")).status_code == 201
    monkeypatch.setenv("DEMO_MAX_REVIEW_RECORDS", "1")
    assert client.post(f"/alerts/{alert.alert_id}/accept", json={"reviewer_id": "synthetic"}).status_code == 201
    assert client.post(f"/alerts/{alert.alert_id}/feedback", json={"reviewer_id": "synthetic", "rating": "helpful"}).status_code == 503
    audit = client.get(f"/alerts/{alert.alert_id}/audit").json()
    assert len(audit["acceptances"]) == 1 and audit["feedback"] == []


def test_sqlite_transaction_enforces_duplicate_ids_across_callers(isolated):
    alert = make_alert(); rules = main.rules_engine.evaluate(alert); result = main.decision_layer.apply(alert, rules)
    def save():
        try: database.log_triage(alert, rules, result); return "saved"
        except database.DuplicateAlertError: return "duplicate"
    with ThreadPoolExecutor(2) as pool:
        a, b = pool.submit(save), pool.submit(save)
        assert sorted([a.result(), b.result()]) == ["duplicate", "saved"]
    assert len(database.load_triage_results()) == 1


def test_unreadable_persisted_decision_is_unavailable_not_empty(isolated, monkeypatch):
    alert = make_alert(); rules = main.rules_engine.evaluate(alert); result = main.decision_layer.apply(alert, rules)
    database.log_triage(alert, rules, result)
    with sqlite3.connect(database.DB_PATH) as conn: conn.execute("UPDATE audit_log SET final_response_json = 'invalid legacy JSON'")
    # Corruption is a local test fixture, never a production mutation path.
    with TestClient(main.app) as client:
        assert client.get("/ready").status_code == 503
        assert client.get("/alerts").status_code == 503
        assert client.get("/health").status_code == 200


def test_per_client_global_windows_and_expiry(monkeypatch):
    from types import SimpleNamespace
    import demo_limits
    clock = SimpleNamespace(now=0)
    monkeypatch.setattr(demo_limits, "time", SimpleNamespace(monotonic=lambda: clock.now))
    limits = DemoLimits(); limits.per_client = 1; limits.global_rate = 2
    assert limits.reserve("client-A") is None; limits.active -= 1
    assert "rate limit" in limits.reserve("client-A")
    assert limits.reserve("client-B") is None; limits.active -= 1
    assert "rate limit" in limits.reserve("client-C")
    clock.now = 61
    assert limits.reserve("client-A") is None


@pytest.mark.asyncio
async def test_total_upload_deadline_returns_408_and_releases_capacity(monkeypatch):
    from types import SimpleNamespace
    import demo_limits
    clock = SimpleNamespace(now=0)
    monkeypatch.setattr(demo_limits, "time", SimpleNamespace(monotonic=lambda: clock.now))
    limits = DemoLimits(); messages = []
    async def inner(*args): raise AssertionError("Timed-out body must not reach the API")
    async def receive():
        clock.now += 6
        return {"type": "http.request", "body": b"a", "more_body": True}
    async def send(message): messages.append(message)
    await DemoLimitMiddleware(inner, limits)({"type": "http", "method": "POST", "client": ("test", 1), "headers": []}, receive, send)
    assert messages[0]["status"] == 408 and limits.active == 0
