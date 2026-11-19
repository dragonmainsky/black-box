from datetime import datetime, timedelta, timezone

from blackbox.probe_types import ProbeResult
from blackbox.store.db import create_engine, init_db
from blackbox.store.probes import insert_probes
from blackbox.store.retention import rollup_completed_hours, run_maintenance

BASE = datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)


def _seed(engine, ts):
    rows = [
        ProbeResult(
            probe="ping",
            target="1.1.1.1",
            value=10.0,
            unit="ms",
            detail={"sent": 3, "recv": 3, "loss_pct": 0.0},
        ),
        ProbeResult(
            probe="ping",
            target="1.1.1.1",
            value=20.0,
            unit="ms",
            detail={"sent": 3, "recv": 3, "loss_pct": 0.0},
        ),
    ]
    insert_probes(engine, rows, ts)


def test_rollup_is_idempotent(tmp_path):
    engine = create_engine(tmp_path)
    init_db(engine)
    _seed(engine, BASE - timedelta(minutes=30))
    assert rollup_completed_hours(engine, BASE) == 1
    assert rollup_completed_hours(engine, BASE) == 0


def test_prune_removes_old_raw(tmp_path):
    engine = create_engine(tmp_path)
    init_db(engine)
    _seed(engine, BASE - timedelta(days=40))
    counts = run_maintenance(engine, BASE, retention_days=30, rollup_days=365)
    assert counts["deleted_probes"] >= 2
