from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from typing import Callable

from blackbox.probe_types import ProbeResult
from blackbox.winio import decode_console

RunFn = Callable[[], tuple[int, str, str]]

_ADDR = r"\d{1,3}(?:\.\d{1,3}){3}"
_MAC = r"[0-9a-fA-F]{2}(?:[-:][0-9a-fA-F]{2}){5}"
_ROW = re.compile(rf"({_ADDR})\s+({_MAC})\s+(\S+)")


@dataclass(frozen=True)
class ArpEntry:
    ip: str
    mac: str
    kind: str


@dataclass(frozen=True)
class ArpSweep:
    result: ProbeResult
    entries: tuple[ArpEntry, ...]


def parse_arp_table(output: str) -> list[ArpEntry]:
    entries: list[ArpEntry] = []
    for line in output.splitlines():
        match = _ROW.search(line)
        if not match:
            continue
        ip, mac, kind = match.groups()
        mac = mac.lower().replace(":", "-")
        if mac == "ff-ff-ff-ff-ff-ff":
            continue
        if ip.startswith("224.") or ip.startswith("239."):
            continue
        entries.append(ArpEntry(ip=ip, mac=mac, kind=kind))
    return entries


def _run_arp() -> tuple[int, str, str]:
    result = subprocess.run(
        ["arp", "-a"],
        capture_output=True,
        timeout=5,
    )
    return (
        result.returncode,
        decode_console(result.stdout),
        decode_console(result.stderr),
    )


def probe_arp(
    run_fn: RunFn | None = None, *, interface: str | None = None
) -> ArpSweep:
    run = run_fn or _run_arp
    try:
        code, output, error = run()
    except Exception:
        return ArpSweep(
            result=ProbeResult(
                probe="arp",
                target="table",
                ok=False,
                interface=interface,
                error_kind="probe_error",
            ),
            entries=(),
        )

    entries = tuple(parse_arp_table(output)) if code == 0 else ()
    result = ProbeResult(
        probe="arp",
        target="table",
        value=float(len(entries)),
        unit="devices",
        ok=code == 0,
        interface=interface,
        detail={
            "devices": [
                {"ip": entry.ip, "mac": entry.mac, "kind": entry.kind}
                for entry in entries
            ]
        },
        error_kind=None if code == 0 else "probe_error",
    )
    return ArpSweep(result=result, entries=entries)
