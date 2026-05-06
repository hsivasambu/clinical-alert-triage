"""
Tests for startup persistence of triage results.

The backend keeps an in-memory store for fast reads, but it should rebuild that
store from SQLite audit history on startup so alerts survive process restarts.
"""

from __future__ import annotations

import uuid
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import database
import main
from tests.conftest import make_alert


def test_load_triage_results_rebuilds_store_from_audit_log(monkeypatch):
    temp_dir = Path(__file__).parent / "_tmp"
    temp_dir.mkdir(exist_ok=True)
    db = temp_dir / f"persistence-{uuid.uuid4().hex}.db"
    try:
        monkeypatch.setattr(database, "DB_PATH", db)
        database.init_db()
        main._store.clear()

        alert = make_alert(alert_id="PERSIST-001")
        result = main.triage_alert(alert)
        assert result.alert_id == "PERSIST-001"
        assert "PERSIST-001" in main._store

        # Simulate a backend restart: memory is gone, persisted audit log remains.
        main._store.clear()
        assert main._store == {}

        restored = database.load_triage_results()
        for item in restored:
            main._store[item.alert_id] = item

        assert "PERSIST-001" in main._store
        assert main._store["PERSIST-001"].alert_id == "PERSIST-001"
        assert main._store["PERSIST-001"].final_priority == result.final_priority
        assert main._store["PERSIST-001"].final_route == result.final_route
    finally:
        main._store.clear()
