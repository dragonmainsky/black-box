from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import insert, select
from sqlalchemy.engine import Engine

from .tables import events


def _iso(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).isoformat()


def insert_gap(
    engine: Engine, ts_start: datetime, ts_end: datetime, gap_seconds: float
) -> int:
    evidence = json.dumps(
        {"gap_seconds": round(gap_seconds, 1), "last_ts": _iso(ts_start)},
        ensure_ascii=False,
    )
    with engine.begin() as conn:
        result = conn.execute(
            insert(events).values(
                ts_start=_iso(ts_start),
                ts_end=_iso(ts_end),
                type="monitor_gap",
                severity="medium",
                title="ระบบไม่ได้เก็บข้อมูลช่วงหนึ่ง",
                details="ระบบอาจถูกปิดหรือเครื่องหลับ",
                evidence=evidence,
            )
        )
        return int(result.inserted_primary_key[0])


def last_gap_start(engine: Engine) -> str | None:
    with engine.connect() as conn:
        row = conn.execute(
            select(events.c.ts_start)
            .where(events.c.type == "monitor_gap")
            .order_by(events.c.id.desc())
            .limit(1)
        ).first()
        return row[0] if row else None


def recent_events(engine: Engine, limit: int = 50) -> list[dict]:
    with engine.connect() as conn:
        rows = (
            conn.execute(select(events).order_by(events.c.id.desc()).limit(limit))
            .mappings()
            .all()
        )
    out = []
    for row in rows:
        item = dict(row)
        if item.get("evidence"):
            item["evidence"] = json.loads(item["evidence"])
        out.append(item)
    return out
