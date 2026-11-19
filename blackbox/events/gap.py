from __future__ import annotations

from datetime import datetime

from sqlalchemy.engine import Engine

from blackbox.store.events import insert_gap


def record_gap_if_needed(
    engine: Engine,
    last_cycle: datetime | None,
    now: datetime,
    interval_s: int,
) -> int | None:
    if last_cycle is None:
        return None
    gap_seconds = (now - last_cycle).total_seconds()
    if gap_seconds <= 2 * interval_s:
        return None
    return insert_gap(engine, last_cycle, now, gap_seconds)
