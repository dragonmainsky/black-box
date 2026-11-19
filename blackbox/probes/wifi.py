from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from typing import Callable

from blackbox.probe_types import ProbeResult
from blackbox.winio import decode_console

RunFn = Callable[[], tuple[int, str, str]]

_KEY_MAP = {
    "state": "state",
    "สถานะ": "state",
    "ssid": "ssid",
    "bssid": "bssid",
    "signal": "signal",
    "สัญญาณ": "signal",
    "receive rate (mbps)": "rx_mbps",
    "อัตราการรับ (mbps)": "rx_mbps",
    "transmit rate (mbps)": "tx_mbps",
    "อัตราการส่ง (mbps)": "tx_mbps",
    "band": "band",
    "แบนด์": "band",
}


@dataclass(frozen=True)
class WifiInfo:
    state: str | None
    ssid: str | None
    bssid: str | None
    signal_pct: float | None
    rx_mbps: float | None
    tx_mbps: float | None
    band: str | None


def _first_number(value: str | None) -> float | None:
    if not value:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)", value)
    return float(match.group(1)) if match else None


def parse_netsh_wifi(output: str) -> WifiInfo | None:
    fields: dict[str, str] = {}
    for line in output.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        canonical = _KEY_MAP.get(key.strip().lower())
        if canonical:
            fields[canonical] = value.strip()

    if "state" not in fields:
        return None

    state = fields.get("state") or None
    ssid = fields.get("ssid") or None
    bssid = fields.get("bssid") or None
    signal_pct = _first_number(fields.get("signal"))
    rx_mbps = _first_number(fields.get("rx_mbps"))
    tx_mbps = _first_number(fields.get("tx_mbps"))
    band = fields.get("band") or None
    return WifiInfo(
        state=state,
        ssid=ssid,
        bssid=bssid,
        signal_pct=signal_pct,
        rx_mbps=rx_mbps,
        tx_mbps=tx_mbps,
        band=band,
    )


def _run_netsh() -> tuple[int, str, str]:
    result = subprocess.run(
        ["netsh", "wlan", "show", "interfaces"],
        capture_output=True,
        timeout=5,
    )
    return (
        result.returncode,
        decode_console(result.stdout),
        decode_console(result.stderr),
    )


def probe_wifi(
    run_fn: RunFn | None = None, *, interface: str | None = None
) -> list[ProbeResult]:
    run = run_fn or _run_netsh
    try:
        code, output, error = run()
    except Exception:
        return [
            ProbeResult(
                probe="wifi",
                target="adapter",
                ok=False,
                interface=interface,
                error_kind="probe_error",
            )
        ]

    info = parse_netsh_wifi(output) if code == 0 else None
    if info is None:
        return [
            ProbeResult(
                probe="wifi",
                target="adapter",
                ok=False,
                interface=interface,
                error_kind="probe_error",
                detail={"stderr": (error or "")[-200:]},
            )
        ]

    rows: list[ProbeResult] = []

    def add_text(target: str, value: str | None) -> None:
        if value is not None:
            rows.append(
                ProbeResult(
                    probe="wifi",
                    target=target,
                    text_value=value,
                    ok=True,
                    interface=interface,
                )
            )

    def add_number(target: str, value: float | None, unit: str) -> None:
        if value is not None:
            rows.append(
                ProbeResult(
                    probe="wifi",
                    target=target,
                    value=value,
                    unit=unit,
                    ok=True,
                    interface=interface,
                )
            )

    add_text("state", info.state)
    add_text("ssid", info.ssid)
    add_text("bssid", info.bssid)
    add_number("signal_pct", info.signal_pct, "%")
    add_number("rx_mbps", info.rx_mbps, "Mbps")
    add_number("tx_mbps", info.tx_mbps, "Mbps")
    add_text("band", info.band)
    return rows
