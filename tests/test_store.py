from datetime import datetime, timezone

from sqlalchemy import inspect

from blackbox.probe_types import ProbeResult
from blackbox.store.db import create_engine, init_db
from blackbox.store.meta import meta_get, meta_set
from blackbox.store.probes import insert_probes, recent_probes


def test_init_db_creates_tables(tmp_path):
    engine = create_engine(tmp_path)
    init_db(engine)
    names = set(inspect(engine).get_table_names())
    assert {"probes", "events", "devices", "probe_rollup", "reports", "meta"} <= names
    assert "alembic_version" in names


def test_insert_probes_batch_and_recent(tmp_path):
    engine = create_engine(tmp_path)
    init_db(engine)
    ts = datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)
    rows = [
        ProbeResult(
            probe="ping",
            target="1.1.1.1",
            value=12.5,
            unit="ms",
            detail={"sent": 3, "recv": 3, "loss_pct": 0.0},
        ),
        ProbeResult(
            probe="dns",
            target="1.1.1.1",
            value=8.0,
            unit="ms",
            detail={"rcode": "NOERROR", "answers": ["93.184.216.34"]},
        ),
    ]
    assert insert_probes(engine, rows, ts) == 2
    recent = recent_probes(engine, limit=10)
    assert len(recent) == 2
    assert recent[0]["probe"] in {"ping", "dns"}
    assert isinstance(recent[0]["detail"], dict)


def test_meta_roundtrip(tmp_path):
    engine = create_engine(tmp_path)
    init_db(engine)
    meta_set(engine, "last_cycle", "2026-11-19T12:00:00+00:00")
    assert meta_get(engine, "last_cycle") == "2026-11-19T12:00:00+00:00"
