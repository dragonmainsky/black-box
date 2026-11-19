from datetime import datetime, timedelta, timezone

from blackbox.probe_types import ProbeResult
from blackbox.store.db import create_engine, init_db
from blackbox.store.probes import insert_probes, ping_window_loss

BASE = datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)


def _result(target, recv):
    return ProbeResult(
        probe="ping",
        target=target,
        value=10.0,
        unit="ms",
        ok=recv > 0,
        detail={"sent": 3, "recv": recv, "loss_pct": 100.0 * (3 - recv) / 3},
    )


def test_window_loss_aggregates_targets(tmp_path):
    engine = create_engine(tmp_path)
    init_db(engine)
    insert_probes(
        engine,
        [
            _result("1.1.1.1", 3),
            _result("1.1.1.1", 2),
            _result("8.8.8.8", 3),
        ],
        BASE,
    )
    loss = ping_window_loss(
        engine, ("1.1.1.1", "8.8.8.8"), BASE - timedelta(minutes=5)
    )
    assert loss.sent == 9
    assert loss.recv == 8
    assert loss.loss_pct == 11.1


def test_window_loss_excludes_old_rows_and_other_targets(tmp_path):
    engine = create_engine(tmp_path)
    init_db(engine)
    insert_probes(engine, [_result("1.1.1.1", 0)], BASE - timedelta(minutes=10))
    insert_probes(engine, [_result("9.9.9.9", 0)], BASE)
    loss = ping_window_loss(
        engine, ("1.1.1.1", "8.8.8.8"), BASE - timedelta(minutes=5)
    )
    assert loss.sent == 0
    assert loss.loss_pct == 0.0