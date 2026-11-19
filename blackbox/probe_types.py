from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

ErrorKind = Literal["network", "timeout", "probe_error", "parse_error"]


@dataclass(frozen=True)
class ProbeResult:
    probe: str
    target: str | None = None
    value: float | None = None
    unit: str | None = None
    ok: bool = True
    interface: str | None = None
    text_value: str | None = None
    detail: dict[str, Any] | None = None
    error_kind: ErrorKind | None = None
