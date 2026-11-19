from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Sequence

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


@dataclass(frozen=True)
class PingLoss:
    sent: int
    recv: int
    loss_pct: float


def ping_window_loss(
    engine: Engine, targets: Sequence[str], since: datetime
) -> PingLoss:
    targets = tuple(dict.fromkeys(targets))
    if not targets:
        return PingLoss(0, 0, 0.0)
    with engine.connect() as conn:
        rows = (
            conn.execute(
                select(probes.c.detail).where(
                    probes.c.probe == "ping",
                    probes.c.target.in_(targets),
                    probes.c.ts >= _iso(since),
                )
            )
            .scalars()
            .all()
        )
    sent = 0
    recv = 0
    for raw in rows:
        if not raw:
            continue
        try:
            detail = json.loads(raw)
        except (TypeError, ValueError):
            continue
        sent += int(detail.get("sent") or 0)
        recv += int(detail.get("recv") or 0)
    loss_pct = round(100.0 * (sent - recv) / sent, 1) if sent else 0.0
    return PingLoss(sent=sent, recv=recv, loss_pct=loss_pct)


def recent_probes(
    engine: Engine, limit: int = 50, probe: str | None = None
) -> list[dict]:
    query = select(probes)
    if probe:
        query = query.where(probes.c.probe == probe)
    query = query.order_by(probes.c.id.desc()).limit(limit)
    with engine.connect() as conn:
        rows = conn.execute(query).mappings().all()
    out = []
    for row in rows:
        item = dict(row)
        if item.get("detail"):
            item["detail"] = json.loads(item["detail"])
        item["ok"] = bool(item["ok"])
        out.append(item)
    return out
