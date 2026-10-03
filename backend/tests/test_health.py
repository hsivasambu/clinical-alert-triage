"""
Tests for the liveness endpoint GET/HEAD /health.

Regression coverage for: Starlette does not auto-add HEAD to a GET-only
route, so an UptimeRobot (or any) monitor using HEAD got a 405 until the
route declared methods=["GET", "HEAD"] explicitly.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from fastapi.testclient import TestClient

import main


@pytest.fixture
def client():
    return TestClient(main.app)


class TestHealth:
    def test_get_returns_200_with_status_body(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "timestamp" in data

    def test_head_returns_200_with_empty_body(self, client):
        resp = client.head("/health")
        assert resp.status_code == 200
        assert resp.content == b""

    def test_head_matches_get_content_length(self, client):
        get_resp = client.get("/health")
        head_resp = client.head("/health")
        assert head_resp.headers.get("content-length") == get_resp.headers.get("content-length")

    def test_post_not_allowed(self, client):
        resp = client.post("/health")
        assert resp.status_code == 405
