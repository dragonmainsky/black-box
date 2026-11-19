"""
Tests for Local API (Phase 2 ข้อ 2)
  - SecurityMiddleware: Host, Origin, Referer, Token
  - Endpoints: /health, /api/status, /api/events, /api/probes
  - token loading/saving
  - run_api host constraint
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from blackbox.api import (
    SecurityMiddleware,
    create_app,
    load_or_create_token,
    run_api,
    save_token,
    token_path,
)
from blackbox.probe_types import ProbeResult
from blackbox.store.db import create_engine, init_db
from blackbox.store.events import open_event
from blackbox.store.meta import meta_set
from blackbox.store.probes import insert_probes

BASE = datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)
TOKEN = "test-token-abc123"


def _make_engine(tmp_path: Path):
    engine = create_engine(tmp_path)
    init_db(engine)
    return engine


def _client(tmp_path: Path, token: str = TOKEN) -> TestClient:
    engine = _make_engine(tmp_path)
    app = create_app(engine, token=token, allowed_hosts={"testserver", "127.0.0.1", "localhost"})
    return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------

def test_save_and_load_token(tmp_path: Path):
    path = token_path(tmp_path)
    save_token(path, "my-secret-token")
    loaded = load_or_create_token(tmp_path)
    assert loaded == "my-secret-token"


def test_load_or_create_generates_token_when_missing(tmp_path: Path):
    t = load_or_create_token(tmp_path)
    assert len(t) > 20
    # Second call returns same token
    t2 = load_or_create_token(tmp_path)
    assert t == t2


def test_token_file_created_on_save(tmp_path: Path):
    path = token_path(tmp_path)
    assert not path.exists()
    save_token(path, "abc")
    assert path.exists()


# ---------------------------------------------------------------------------
# /health – no token required
# ---------------------------------------------------------------------------

def test_health_no_token(tmp_path: Path):
    client = _client(tmp_path)
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"ok": True}


# ---------------------------------------------------------------------------
# Host header validation
# ---------------------------------------------------------------------------

def test_reject_bad_host(tmp_path: Path):
    engine = _make_engine(tmp_path)
    app = create_app(engine, token=TOKEN, allowed_hosts={"127.0.0.1"})
    client = TestClient(app, raise_server_exceptions=True)
    res = client.get(
        "/api/status",
        headers={"host": "evil.example.com", "Authorization": f"Bearer {TOKEN}"},
    )
    assert res.status_code == 403


# ---------------------------------------------------------------------------
# Token authentication
# ---------------------------------------------------------------------------

def test_bearer_token_accepted(tmp_path: Path):
    client = _client(tmp_path)
    res = client.get("/api/status", headers={"Authorization": f"Bearer {TOKEN}"})
    assert res.status_code == 200


def test_x_api_token_accepted(tmp_path: Path):
    client = _client(tmp_path)
    res = client.get("/api/status", headers={"X-API-Token": TOKEN})
    assert res.status_code == 200


def test_query_token_accepted(tmp_path: Path):
    client = _client(tmp_path)
    res = client.get(f"/api/status?token={TOKEN}")
    assert res.status_code == 200


def test_missing_token_returns_401(tmp_path: Path):
    client = _client(tmp_path)
    res = client.get("/api/status")
    assert res.status_code == 401


def test_wrong_token_returns_401(tmp_path: Path):
    client = _client(tmp_path)
    res = client.get("/api/status", headers={"Authorization": "Bearer wrong-token"})
    assert res.status_code == 401


# ---------------------------------------------------------------------------
# Origin / Referer validation
# ---------------------------------------------------------------------------

def test_reject_cross_origin(tmp_path: Path):
    client = _client(tmp_path)
    res = client.get(
        "/api/status",
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Origin": "http://evil.example.com",
        },
    )
    assert res.status_code == 403


def test_allow_null_origin(tmp_path: Path):
    client = _client(tmp_path)
    res = client.get(
        "/api/status",
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Origin": "null",
        },
    )
    assert res.status_code == 200


def test_reject_cross_referer(tmp_path: Path):
    client = _client(tmp_path)
    res = client.get(
        "/api/status",
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Referer": "http://evil.example.com/page",
        },
    )
    assert res.status_code == 403


# ---------------------------------------------------------------------------
# /api/status endpoint
# ---------------------------------------------------------------------------

def test_status_empty_db(tmp_path: Path):
    client = _client(tmp_path)
    res = client.get("/api/status", headers={"Authorization": f"Bearer {TOKEN}"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "unknown"
    assert data["open_events"] == []


def test_status_with_probes(tmp_path: Path):
    engine = _make_engine(tmp_path)
    meta_set(engine, "last_interface", "Wi-Fi")
    meta_set(engine, "last_gateway", "192.168.1.1")
    meta_set(engine, "last_cycle", BASE.isoformat())
    insert_probes(
        engine,
        [ProbeResult(probe="ping", target="192.168.1.1", value=2.5, ok=True)],
        BASE,
    )
    app = create_app(engine, token=TOKEN, allowed_hosts={"testserver", "127.0.0.1"})
    client = TestClient(app)
    res = client.get("/api/status", headers={"Authorization": f"Bearer {TOKEN}"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["interface"] == "Wi-Fi"
    assert data["gateway"] == "192.168.1.1"


def test_status_critical_on_open_event(tmp_path: Path):
    engine = _make_engine(tmp_path)
    insert_probes(
        engine,
        [ProbeResult(probe="ping", target="1.1.1.1", ok=True, value=5.0)],
        BASE,
    )
    open_event(
        engine,
        event_type="gateway_down",
        severity="high",
        title="เราเตอร์ไม่ตอบ",
        details="",
        evidence={"gateway": "192.168.1.1", "failures": 3},
        ts=BASE,
    )
    app = create_app(engine, token=TOKEN, allowed_hosts={"testserver", "127.0.0.1"})
    client = TestClient(app)
    res = client.get("/api/status", headers={"Authorization": f"Bearer {TOKEN}"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "critical"
    assert len(data["open_events"]) == 1
    assert "ไม่ตอบสนอง ping" in data["open_events"][0]["narrative"]


# ---------------------------------------------------------------------------
# /api/events endpoint
# ---------------------------------------------------------------------------

def test_events_empty(tmp_path: Path):
    client = _client(tmp_path)
    res = client.get("/api/events", headers={"Authorization": f"Bearer {TOKEN}"})
    assert res.status_code == 200
    assert res.json() == []


def test_events_returns_list_with_narrative(tmp_path: Path):
    engine = _make_engine(tmp_path)
    open_event(
        engine,
        event_type="internet_down",
        severity="high",
        title="อินเทอร์เน็ตหลุด",
        details="",
        evidence={"targets": ["1.1.1.1"], "failures": 3},
        ts=BASE,
    )
    app = create_app(engine, token=TOKEN, allowed_hosts={"testserver", "127.0.0.1"})
    client = TestClient(app)
    res = client.get("/api/events", headers={"Authorization": f"Bearer {TOKEN}"})
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["type"] == "internet_down"
    assert "narrative" in data[0]
    assert "อินเทอร์เน็ตหลุด" in data[0]["narrative"]


def test_events_open_only(tmp_path: Path):
    from datetime import timedelta

    from blackbox.store.events import close_event

    engine = _make_engine(tmp_path)
    # Closed event
    ev_id = open_event(
        engine,
        event_type="dns_fail",
        severity="high",
        title="DNS ล่ม",
        details="",
        evidence={},
        ts=BASE - timedelta(minutes=10),
    )
    close_event(engine, ev_id, BASE - timedelta(minutes=5))
    # Open event
    open_event(
        engine,
        event_type="gateway_down",
        severity="high",
        title="เราเตอร์ไม่ตอบ",
        details="",
        evidence={"gateway": "192.168.1.1", "failures": 3},
        ts=BASE,
    )
    app = create_app(engine, token=TOKEN, allowed_hosts={"testserver", "127.0.0.1"})
    client = TestClient(app)
    res = client.get(
        "/api/events?open_only=true",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["type"] == "gateway_down"


def test_events_filter_by_type(tmp_path: Path):
    engine = _make_engine(tmp_path)
    open_event(
        engine,
        event_type="dns_slow",
        severity="medium",
        title="DNS ช้า",
        details="",
        evidence={},
        ts=BASE,
    )
    open_event(
        engine,
        event_type="gateway_down",
        severity="high",
        title="เราเตอร์ไม่ตอบ",
        details="",
        evidence={},
        ts=BASE,
    )
    app = create_app(engine, token=TOKEN, allowed_hosts={"testserver", "127.0.0.1"})
    client = TestClient(app)
    res = client.get(
        "/api/events?type=dns_slow",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["type"] == "dns_slow"


# ---------------------------------------------------------------------------
# /api/probes endpoint
# ---------------------------------------------------------------------------

def test_probes_empty(tmp_path: Path):
    client = _client(tmp_path)
    res = client.get("/api/probes", headers={"Authorization": f"Bearer {TOKEN}"})
    assert res.status_code == 200
    assert res.json() == []


def test_probes_returns_records(tmp_path: Path):
    engine = _make_engine(tmp_path)
    insert_probes(
        engine,
        [
            ProbeResult(probe="ping", target="1.1.1.1", value=10.0, ok=True),
            ProbeResult(probe="dns", target="1.1.1.1", value=25.0, ok=True),
        ],
        BASE,
    )
    app = create_app(engine, token=TOKEN, allowed_hosts={"testserver", "127.0.0.1"})
    client = TestClient(app)
    res = client.get("/api/probes", headers={"Authorization": f"Bearer {TOKEN}"})
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 2
    assert any(r["probe"] == "ping" for r in data)


def test_probes_filter_by_probe(tmp_path: Path):
    engine = _make_engine(tmp_path)
    insert_probes(
        engine,
        [
            ProbeResult(probe="ping", target="1.1.1.1", value=10.0, ok=True),
            ProbeResult(probe="dns", target="1.1.1.1", value=25.0, ok=True),
        ],
        BASE,
    )
    app = create_app(engine, token=TOKEN, allowed_hosts={"testserver", "127.0.0.1"})
    client = TestClient(app)
    res = client.get("/api/probes?probe=ping", headers={"Authorization": f"Bearer {TOKEN}"})
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["probe"] == "ping"


# ---------------------------------------------------------------------------
# run_api host constraint
# ---------------------------------------------------------------------------

def test_run_api_rejects_non_loopback_host(tmp_path: Path):
    engine = _make_engine(tmp_path)
    with pytest.raises(ValueError, match="127.0.0.1"):
        run_api(engine, host="0.0.0.0", token=TOKEN)
