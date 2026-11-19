from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import case, delete, func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine

from .meta import meta_get, meta_set
from .tables import events, probe_rollup, probes


def _iso(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).isoformat()


def _hour_start(ts: datetime) -> datetime:
    return ts.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)


def rollup_completed_hours(engine: Engine, now: datetime) -> int:
    now = now.astimezone(timezone.utc)
    current_hour = _hour_start(now)

    last = meta_get(engine, "last_rollup_hour")
    if last:
        start = datetime.fromisoformat(last)
    else:
        with engine.connect() as conn:
            first = conn.execute(select(func.min(probes.c.ts))).scalar()
        if not first:
            return 0
        start = _hour_start(datetime.fromisoformat(first))

    if start >= current_hour:
        return 0

    hour_expr = func.substr(probes.c.ts, 1, 13)
    target_expr = func.coalesce(probes.c.target, "")
    loss_expr = (
        100.0
        * func.sum(case((probes.c.ok == 0, 1), else_=0))
        / func.count()
    )
    stmt = (
        select(
            hour_expr.label("hour"),
            probes.c.probe,
            target_expr.label("target"),
            func.avg(probes.c.value).label("avg_value"),
            func.min(probes.c.value).label("min_value"),
            func.max(probes.c.value).label("max_value"),
            loss_expr.label("loss_pct"),
            func.count().label("samples"),
        )
        .where(
            probes.c.ts >= _iso(start),
            probes.c.ts < _iso(current_hour),
        )
        .group_by(hour_expr, probes.c.probe, target_expr)
    )

    with engine.begin() as conn:
        rows = conn.execute(stmt).mappings().all()
        for row in rows:
            hour = row["hour"] + ":00:00+00:00"
            stmt2 = sqlite_insert(probe_rollup).values(
                hour=hour,
                probe=row["probe"],
                target=row["target"],
                avg_value=row["avg_value"],
                min_value=row["min_value"],
                max_value=row["max_value"],
                loss_pct=row["loss_pct"],
                samples=row["samples"],
            )
            stmt2 = stmt2.on_conflict_do_update(
                index_elements=["hour", "probe", "target"],
                set_={
                    "avg_value": row["avg_value"],
                    "min_value": row["min_value"],
                    "max_value": row["max_value"],
                    "loss_pct": row["loss_pct"],
                    "samples": row["samples"],
                },
            )
            conn.execute(stmt2)

    meta_set(engine, "last_rollup_hour", _iso(current_hour))
    return len({row["hour"] for row in rows})


def prune(
    engine: Engine,
    now: datetime,
    *,
    retention_days: int,
    rollup_days: int,
) -> dict[str, int]:
    now = now.astimezone(timezone.utc)
    probe_cutoff = _iso(now - timedelta(days=retention_days))
    rollup_cutoff = _iso(now - timedelta(days=rollup_days))

    deleted_probes = 0
    while True:
        with engine.begin() as conn:
            ids = (
                conn.execute(
                    select(probes.c.id)
                    .where(probes.c.ts < probe_cutoff)
                    .limit(5000)
                )
                .scalars()
                .all()
            )
            if not ids:
                break
            result = conn.execute(delete(probes).where(probes.c.id.in_(ids)))
            deleted_probes += result.rowcount or 0

    with engine.begin() as conn:
        rollup_result = conn.execute(
            delete(probe_rollup).where(probe_rollup.c.hour < rollup_cutoff)
        )
        event_result = conn.execute(
            delete(events).where(events.c.ts_start < rollup_cutoff)
        )

    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA optimize")

    return {
        "deleted_probes": deleted_probes,
        "deleted_rollups": rollup_result.rowcount or 0,
        "deleted_events": event_result.rowcount or 0,
    }


def run_maintenance(
    engine: Engine,
    now: datetime,
    *,
    retention_days: int,
    rollup_days: int,
    vacuum: bool = False,
) -> dict[str, int]:
    now = now.astimezone(timezone.utc)
    rolled = rollup_completed_hours(engine, now)
    counts = prune(
        engine, now, retention_days=retention_days, rollup_days=rollup_days
    )
    counts["rolled_up_hours"] = rolled
    meta_set(engine, "last_maintenance", _iso(now))

    last_vacuum = meta_get(engine, "last_vacuum")
    due = vacuum
    if not due and last_vacuum:
        due = (now - datetime.fromisoformat(last_vacuum)) >= timedelta(days=30)
    if due:
        with engine.connect().execution_options(
            isolation_level="AUTOCOMMIT"
        ) as conn:
            conn.exec_driver_sql("VACUUM")
        meta_set(engine, "last_vacuum", _iso(now))
        counts["vacuumed"] = 1
    return counts
