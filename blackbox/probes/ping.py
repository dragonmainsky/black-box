from __future__ import annotations

import ctypes
import socket
from ctypes import wintypes
from typing import Protocol, Sequence

from blackbox.probe_types import ProbeResult


class EchoSender(Protocol):
    def send(self, target: str, timeout_ms: int) -> float | None: ...


class IP_OPTION_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("Ttl", ctypes.c_ubyte),
        ("Tos", ctypes.c_ubyte),
        ("Flags", ctypes.c_ubyte),
        ("OptionsSize", ctypes.c_ubyte),
        ("OptionsData", ctypes.c_void_p),
    ]


class ICMP_ECHO_REPLY(ctypes.Structure):
    _fields_ = [
        ("Address", wintypes.ULONG),
        ("Status", wintypes.ULONG),
        ("RoundTripTime", wintypes.ULONG),
        ("DataSize", wintypes.USHORT),
        ("Reserved", wintypes.USHORT),
        ("Data", ctypes.c_void_p),
        ("Options", IP_OPTION_INFORMATION),
    ]


class WindowsEchoSender:
    """ICMP echo ผ่าน IcmpSendEcho — ไม่ต้อง admin และไม่พึ่ง ping.exe"""

    def __init__(self) -> None:
        if not hasattr(ctypes, "windll"):
            raise OSError("Windows ICMP API ไม่พร้อมใช้งาน")
        self._iphlpapi = ctypes.windll.iphlpapi
        self._iphlpapi.IcmpCreateFile.restype = wintypes.HANDLE
        self._iphlpapi.IcmpCloseHandle.argtypes = [wintypes.HANDLE]
        self._iphlpapi.IcmpSendEcho.argtypes = [
            wintypes.HANDLE,
            wintypes.ULONG,
            ctypes.c_void_p,
            wintypes.WORD,
            ctypes.POINTER(IP_OPTION_INFORMATION),
            ctypes.c_void_p,
            wintypes.DWORD,
            wintypes.DWORD,
        ]
        self._iphlpapi.IcmpSendEcho.restype = wintypes.DWORD
        self._handle = self._iphlpapi.IcmpCreateFile()
        invalid = ctypes.c_void_p(-1).value
        if not self._handle or self._handle == invalid:
            raise OSError("IcmpCreateFile ล้มเหลว")

    def send(self, target: str, timeout_ms: int) -> float | None:
        if not self._handle:
            return None
        address = int.from_bytes(socket.inet_aton(target), "little")
        request = ctypes.create_string_buffer(b"blackbox")
        reply = ctypes.create_string_buffer(ctypes.sizeof(ICMP_ECHO_REPLY) + 64)
        # Pass NULL options: a zeroed IP_OPTION_INFORMATION sets TTL=0
        # and Windows answers IP_TTL_EXPIRED_TRANSIT (11013).
        count = self._iphlpapi.IcmpSendEcho(
            self._handle,
            address,
            request,
            len(request) - 1,
            None,
            reply,
            len(reply),
            timeout_ms,
        )
        if count == 0:
            return None
        echo = ctypes.cast(reply, ctypes.POINTER(ICMP_ECHO_REPLY)).contents
        if echo.Status != 0:
            return None
        return float(echo.RoundTripTime)

    def close(self) -> None:
        if self._handle:
            self._iphlpapi.IcmpCloseHandle(self._handle)
            self._handle = None

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass


def ping_targets(
    targets: Sequence[str],
    sender: EchoSender,
    *,
    interface: str | None = None,
    echo_count: int = 3,
    timeout_ms: int = 2000,
) -> list[ProbeResult]:
    results: list[ProbeResult] = []
    for target in targets:
        rtts: list[float] = []
        try:
            for _ in range(echo_count):
                rtt = sender.send(target, timeout_ms)
                if rtt is not None:
                    rtts.append(float(rtt))
        except Exception:
            results.append(
                ProbeResult(
                    probe="ping",
                    target=target,
                    ok=False,
                    interface=interface,
                    error_kind="probe_error",
                )
            )
            continue

        recv = len(rtts)
        sent = echo_count
        loss_pct = round(100.0 * (sent - recv) / sent, 1) if sent else 0.0
        detail = {"sent": sent, "recv": recv, "loss_pct": loss_pct, "rtts_ms": rtts}
        if recv == 0:
            results.append(
                ProbeResult(
                    probe="ping",
                    target=target,
                    ok=False,
                    interface=interface,
                    detail=detail,
                    error_kind="network",
                )
            )
            continue
        results.append(
            ProbeResult(
                probe="ping",
                target=target,
                value=round(sum(rtts) / recv, 2),
                unit="ms",
                ok=True,
                interface=interface,
                detail=detail,
            )
        )
    return results
