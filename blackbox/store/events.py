from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Sequence

from sqlalchemy import insert, select, update
from sqlalchemy.engine import Engine

from .tables import events

if TYPE_CHECKING:
    from blackbox.events.rules import EventAction


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


def open_event(
    engine: Engine,
    event_type: str,
    severity: str,
    title: str,
    details: str,
    evidence: dict,
    ts: datetime,
) -> int:
    with engine.begin() as conn:
        result = conn.execute(
            insert(events).values(
                ts_start=_iso(ts),
                type=event_type,
                severity=severity,
                title=title,
                details=details,
                evidence=json.dumps(evidence, ensure_ascii=False),
            )
        )
        return int(result.inserted_primary_key[0])


def find_open_event(engine: Engine, event_type: str) -> dict | None:
    with engine.connect() as conn:
        row = (
            conn.execute(
                select(events)
                .where(
                    events.c.type == event_type,
                    events.c.ts_end.is_(None),
                )
                .order_by(events.c.id.desc())
                .limit(1)
            )
            .mappings()
            .first()
        )
    if row is None:
        return None
    item = dict(row)
    if item.get("evidence"):
        item["evidence"] = json.loads(item["evidence"])
    return item


def close_event(engine: Engine, event_id: int, ts: datetime) -> None:
    with engine.begin() as conn:
        conn.execute(
            update(events)
            .where(events.c.id == event_id)
            .values(ts_end=_iso(ts))
        )


def open_event_types(engine: Engine) -> list[str]:
    with engine.connect() as conn:
        rows = (
            conn.execute(
                select(events.c.type).where(events.c.ts_end.is_(None))
            )
            .scalars()
            .all()
        )
    return list(dict.fromkeys(rows))


def apply_actions(
    engine: Engine, actions: Sequence["EventAction"]
) -> list[int]:
    ids: list[int] = []
    for action in actions:
        existing = find_open_event(engine, action.type)
        if action.action == "open":
            if existing:
                ids.append(int(existing["id"]))
                continue
            ids.append(
                open_event(
                    engine,
                    action.type,
                    action.severity,
                    action.title,
                    action.details,
                    action.evidence,
                    action.ts,
                )
            )
        else:
            if existing:
                close_event(engine, int(existing["id"]), action.ts)
                ids.append(int(existing["id"]))
    return ids


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
