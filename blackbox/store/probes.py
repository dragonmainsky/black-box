from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import insert, select
from sqlalchemy.engine import Engine

from blackbox.probe_types import ProbeResult

from .tables import probes


def _iso(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).isoformat()


def insert_probes(engine: Engine, results: Iterable[ProbeResult], ts: datetime) -> int:
    rows = []
    for result in results:
        rows.append(
            {
                "ts": _iso(ts),
                "probe": result.probe,
                "target": result.target,
                "value": result.value,
                "unit": result.unit,
                "ok": 1 if result.ok else 0,
                "interface": result.interface,
                "text_value": result.text_value,
                "detail": (
                    json.dumps(result.detail, ensure_ascii=False)
                    if result.detail is not None
                    else None
                ),
                "error_kind": result.error_kind,
            }
        )
    if not rows:
        return 0
    with engine.begin() as conn:
        conn.execute(insert(probes), rows)
    return len(rows)


def recent_probes(engine: Engine, limit: int = 50) -> list[dict]:
    with engine.connect() as conn:
        rows = (
            conn.execute(select(probes).order_by(probes.c.id.desc()).limit(limit))
            .mappings()
            .all()
        )
    out = []
    for row in rows:
        item = dict(row)
        if item.get("detail"):
            item["detail"] = json.loads(item["detail"])
        item["ok"] = bool(item["ok"])
        out.append(item)
    return out
