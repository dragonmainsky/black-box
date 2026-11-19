from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.engine import Engine

from blackbox.events.narrator import narrate_event
from blackbox.store.events import get_open_events, recent_events
from blackbox.store.meta import meta_get
from blackbox.store.probes import recent_probes
from blackbox.store.tables import devices, probes


@dataclass
class SystemStatus:
    status: str  # "ok" | "warning" | "critical" | "unknown"
    status_text: str  # "ปกติ" | "เตือน" | "วิกฤต" | "ยังไม่มีข้อมูล"
    last_cycle: str | None
    interface: str | None
    gateway: str | None
    public_ip: str | None
    device_count: int
    open_events: list[dict[str, Any]]
    recent_events: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def get_system_status(engine: Engine, recent_limit: int = 5) -> SystemStatus:
    # 1. Open events
    open_evts = get_open_events(engine)
    for evt in open_evts:
        evt["narrative"] = narrate_event(evt)

    # 2. Recent events
    rec_evts = recent_events(engine, limit=recent_limit)
    for evt in rec_evts:
        evt["narrative"] = narrate_event(evt)

    # 3. Meta info
    last_cycle = meta_get(engine, "last_cycle")
    interface = meta_get(engine, "last_interface")
    gateway = meta_get(engine, "last_gateway")
    public_ip = meta_get(engine, "last_public_ip")

    latest_probe = recent_probes(engine, limit=1)
    if not last_cycle and latest_probe:
        last_cycle = latest_probe[0]["ts"]

    # 4. Counts
    with engine.connect() as conn:
        device_count = (
            conn.execute(select(func.count(devices.c.id))).scalar() or 0
        )
        probe_count = (
            conn.execute(select(func.count(probes.c.id))).scalar() or 0
        )

    # 5. Evaluate overall health
    if probe_count == 0 and not open_evts and not rec_evts:
        status = "unknown"
        status_text = "ยังไม่มีข้อมูล"
    elif any(e.get("severity") == "high" for e in open_evts):
        status = "critical"
        status_text = "วิกฤต"
    elif any(e.get("severity") in ("medium", "low") for e in open_evts):
        status = "warning"
        status_text = "เตือน"
    elif open_evts:
        status = "info"
        status_text = "พบปัญหา"
    else:
        status = "ok"
        status_text = "ปกติ"

    return SystemStatus(
        status=status,
        status_text=status_text,
        last_cycle=last_cycle,
        interface=interface,
        gateway=gateway,
        public_ip=public_ip,
        device_count=device_count,
        open_events=open_evts,
        recent_events=rec_evts,
    )
