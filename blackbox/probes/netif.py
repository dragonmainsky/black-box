from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Callable

RunFn = Callable[[], tuple[int, str, str]]

_ROUTE_CMD = (
    "Get-NetRoute -DestinationPrefix '0.0.0.0/0' | "
    "Sort-Object RouteMetric | Select-Object -First 1 "
    "InterfaceAlias,InterfaceIndex,NextHop,RouteMetric | ConvertTo-Json -Compress"
)
_DNS_CMD = (
    "Get-DnsClientServerAddress -AddressFamily IPv4 | "
    "Select-Object InterfaceAlias,ServerAddresses | ConvertTo-Json -Compress"
)


@dataclass(frozen=True)
class InterfaceInfo:
    alias: str
    index: int
    gateway: str | None
    is_wifi: bool


def _run_powershell(command: str) -> tuple[int, str, str]:
    result = subprocess.run(
        [
            "powershell",
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            command,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=5,
    )
    return result.returncode, result.stdout, result.stderr


def _as_list(data):
    if isinstance(data, dict):
        return [data]
    return data if isinstance(data, list) else []


def parse_route_json(raw: str) -> InterfaceInfo | None:
    data = _as_list(json.loads(raw))
    if not data:
        return None
    best = min(data, key=lambda item: int(item.get("RouteMetric") or 9999))
    alias = str(best.get("InterfaceAlias") or "")
    lowered = alias.lower()
    is_wifi = any(token in lowered for token in ("wi-fi", "wifi", "wireless", "wlan"))
    return InterfaceInfo(
        alias=alias,
        index=int(best.get("InterfaceIndex") or 0),
        gateway=best.get("NextHop") or None,
        is_wifi=is_wifi,
    )


def parse_dns_json(raw: str, alias: str) -> list[str]:
    data = _as_list(json.loads(raw))
    for item in data:
        if str(item.get("InterfaceAlias") or "") != alias:
            continue
        servers = item.get("ServerAddresses") or []
        if isinstance(servers, str):
            servers = [servers]
        unique: list[str] = []
        for server in servers:
            value = str(server)
            if value not in unique:
                unique.append(value)
        return unique
    return []


def detect_interface(run_fn: RunFn | None = None) -> InterfaceInfo | None:
    run = run_fn or (lambda: _run_powershell(_ROUTE_CMD))
    try:
        code, output, _error = run()
    except Exception:
        return None
    if code != 0 or not output.strip():
        return None
    try:
        return parse_route_json(output)
    except (ValueError, TypeError):
        return None


def detect_dns_servers(alias: str, run_fn: RunFn | None = None) -> list[str]:
    run = run_fn or (lambda: _run_powershell(_DNS_CMD))
    try:
        code, output, _error = run()
    except Exception:
        return []
    if code != 0 or not output.strip():
        return []
    try:
        return parse_dns_json(output, alias)
    except (ValueError, TypeError):
        return []
