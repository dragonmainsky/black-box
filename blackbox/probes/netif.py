from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Callable

from blackbox.winio import decode_console

RunFn = Callable[[], tuple[int, str, str]]

_ROUTE_CMD = (
    "Get-NetRoute -DestinationPrefix '0.0.0.0/0' | "
    "Select-Object InterfaceAlias,InterfaceIndex,NextHop,RouteMetric,InterfaceMetric | "
    "ConvertTo-Json -Compress"
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
        timeout=5,
    )
    return (
        result.returncode,
        decode_console(result.stdout),
        decode_console(result.stderr),
    )


def _as_list(data):
    if isinstance(data, dict):
        return [data]
    return data if isinstance(data, list) else []


def _effective_metric(item: dict) -> int:
    route = item.get("RouteMetric")
    interface = item.get("InterfaceMetric")
    route_value = int(route) if route is not None else 9999
    interface_value = int(interface) if interface is not None else 0
    return route_value + interface_value


def parse_route_json(raw: str) -> InterfaceInfo | None:
    data = _as_list(json.loads(raw))
    candidates = [
        item
        for item in data
        if str(item.get("NextHop") or "") not in ("", "0.0.0.0")
    ]
    if not candidates:
        return None
    best = min(candidates, key=_effective_metric)
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
