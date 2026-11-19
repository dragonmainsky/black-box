from __future__ import annotations

import ipaddress
import urllib.request
from typing import Callable

from blackbox.probe_types import ProbeResult

FetchFn = Callable[[], str]


def _fetch_ip(timeout_s: float) -> str:
    with urllib.request.urlopen("https://api.ipify.org", timeout=timeout_s) as response:
        return response.read().decode("ascii", "replace").strip()


def probe_public_ip(
    fetch_fn: FetchFn | None = None, *, timeout_s: float = 5.0
) -> ProbeResult:
    fetch = fetch_fn or (lambda: _fetch_ip(timeout_s))
    try:
        raw = fetch()
    except TimeoutError:
        return ProbeResult(
            probe="public_ip",
            target="ipify",
            ok=False,
            error_kind="timeout",
        )
    except OSError:
        return ProbeResult(
            probe="public_ip",
            target="ipify",
            ok=False,
            error_kind="network",
        )
    except Exception:
        return ProbeResult(
            probe="public_ip",
            target="ipify",
            ok=False,
            error_kind="probe_error",
        )

    try:
        value = str(ipaddress.ip_address(raw.strip()))
    except ValueError:
        return ProbeResult(
            probe="public_ip",
            target="ipify",
            ok=False,
            text_value=raw,
            error_kind="parse_error",
        )
    return ProbeResult(
        probe="public_ip",
        target="ipify",
        ok=True,
        text_value=value,
    )
