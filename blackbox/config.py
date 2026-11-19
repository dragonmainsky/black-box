from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ALLOWED_TARGETS = frozenset({"1.1.1.1", "8.8.8.8"})


@dataclass(frozen=True)
class Config:
    data_dir: Path
    base_interval_s: int = 30
    dns_interval_s: int = 60
    wifi_interval_s: int = 300
    arp_interval_s: int = 300
    public_ip_interval_s: int = 900
    public_ip_enabled: bool = False
    retention_days: int = 30
    rollup_retention_days: int = 365
    monitor_interface: str = "auto"
    targets: tuple[str, ...] = ("1.1.1.1", "8.8.8.8")
    echo_count: int = 3
    echo_timeout_ms: int = 2000

    def validate(self) -> None:
        if not 10 <= self.base_interval_s <= 3600:
            raise ValueError("base_interval_s ต้องอยู่ระหว่าง 10–3600 วินาที")
        for name in ("dns_interval_s", "wifi_interval_s", "arp_interval_s", "public_ip_interval_s"):
            if getattr(self, name) < self.base_interval_s:
                raise ValueError(f"{name} ต้องไม่น้อยกว่า base_interval_s")
        if not 1 <= self.retention_days <= 3650:
            raise ValueError("retention_days ต้องอยู่ระหว่าง 1–3650 วัน")
        if not 1 <= self.rollup_retention_days <= 3650:
            raise ValueError("rollup_retention_days ต้องอยู่ระหว่าง 1–3650 วัน")
        if self.echo_count < 1:
            raise ValueError("echo_count ต้องมากกว่า 0")
        if self.echo_timeout_ms < 100:
            raise ValueError("echo_timeout_ms ต้องอย่างน้อย 100 ms")
        unknown = set(self.targets) - ALLOWED_TARGETS
        if unknown:
            raise ValueError(f"target ไม่อยู่ใน allowlist: {sorted(unknown)}")
