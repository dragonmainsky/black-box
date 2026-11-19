from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.engine import Engine

from blackbox.store.events import insert_gap, last_gap_start


def _iso(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).isoformat()


def record_gap_if_needed(
    engine: Engine,
    last_cycle: datetime | None,
    now: datetime,
    interval_s: int,
) -> int | None:
    if last_cycle is None:
        return None
    if now <= last_cycle:
        return None
    gap_seconds = (now - last_cycle).total_seconds()
    if gap_seconds <= 2 * interval_s:
        return None
    if last_gap_start(engine) == _iso(last_cycle):
        return None
    return insert_gap(engine, last_cycle, now, gap_seconds)
