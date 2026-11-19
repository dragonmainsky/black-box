from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from statistics import median
from typing import Any, Iterable, Literal, Sequence

from blackbox.probe_types import ProbeResult

ActionName = Literal["open", "close"]

_RULES: dict[str, tuple[str, str, str]] = {
    "gateway_down": ("high", "เน็ตหลุดที่ gateway", "เราเตอร์ไม่ตอบ ping ต่อเนื่อง"),
    "internet_down": (
        "high",
        "อินเทอร์เน็ตหลุด",
        "gateway ตอบ แต่ปลายทางอินเทอร์เน็ตไม่ตอบ",
    ),
    "dns_fail": ("high", "DNS ล่ม", "DNS resolver ตอบไม่ได้"),
    "dns_slow": ("medium", "DNS ตอบช้า", "DNS ใช้เวลาเกิน 1 วินาที"),
    "wifi_drop": (
        "medium",
        "Wi-Fi หลุด/สัญญาณอ่อน",
        "Wi-Fi หลุดหรือสัญญาณต่ำกว่า 30%",
    ),
    "latency_spike": (
        "medium",
        "Latency พุ่ง",
        "ค่า latency สูงกว่าปกติเกิน 3 เท่า",
    ),
    "packet_loss": (
        "high",
        "Packet loss สูง",
        "อัตราแพ็กเก็ตหายเกิน 5% ใน 5 นาที",
    ),
    "new_device": (
        "low",
        "พบอุปกรณ์ใหม่",
        "พบ MAC address ที่ไม่เคยเห็นในเครือข่าย",
    ),
    "public_ip_change": (
        "low",
        "Public IP เปลี่ยน",
        "หมายเลข Public IP มีการเปลี่ยนแปลง",
    ),
    "interface_change": (
        "low",
        "เปลี่ยนอินเทอร์เฟซ",
        "เกตเวย์หรืออินเทอร์เฟซหลักมีการเปลี่ยนแปลง",
    ),
}


@dataclass(frozen=True)
class EventAction:
    action: ActionName
    type: str
    severity: str
    title: str
    details: str
    evidence: dict[str, Any]
    ts: datetime


class RuleEngine:
    def __init__(
        self,
        *,
        gateway: str | None = None,
        internet_targets: Sequence[str] = ("1.1.1.1", "8.8.8.8"),
        wifi_monitored: bool = False,
        open_types: Iterable[str] = (),
        latency_baseline_samples: int = 10,
    ) -> None:
        self.gateway = gateway
        self.internet_targets = tuple(internet_targets)
        self.wifi_monitored = wifi_monitored
        self._open_types = set(open_types)
        self._latency_baseline_samples = max(2, latency_baseline_samples)
        self._gateway_fail = 0
        self._internet_fail = 0
        self._dns_fail = 0
        self._dns_slow = 0
        self._wifi_low = 0
        self._latency_samples: list[float] = []

    # ---------- helpers ----------

    @staticmethod
    def _find(
        results: Sequence[ProbeResult], probe: str, target: str
    ) -> ProbeResult | None:
        for result in results:
            if result.probe == probe and result.target == target:
                return result
        return None

    def _open_action(
        self, event_type: str, evidence: dict[str, Any], ts: datetime
    ) -> EventAction | None:
        if event_type in self._open_types:
            return None
        severity, title, details = _RULES[event_type]
        self._open_types.add(event_type)
        return EventAction(
            action="open",
            type=event_type,
            severity=severity,
            title=title,
            details=details,
            evidence=evidence,
            ts=ts,
        )

    def _close_action(
        self, event_type: str, evidence: dict[str, Any], ts: datetime
    ) -> EventAction | None:
        if event_type not in self._open_types:
            return None
        severity, title, details = _RULES[event_type]
        self._open_types.discard(event_type)
        return EventAction(
            action="close",
            type=event_type,
            severity=severity,
            title=title,
            details=details,
            evidence={"recovered": True, **evidence},
            ts=ts,
        )

    def _open_event(
        self, event_type: str, evidence: dict[str, Any], now: datetime
    ) -> list[EventAction]:
        action = self._open_action(event_type, evidence, now)
        return [action] if action else []

    def _close_event(
        self, event_type: str, evidence: dict[str, Any], now: datetime
    ) -> list[EventAction]:
        action = self._close_action(event_type, evidence, now)
        return [action] if action else []

    # ---------- rules ----------

    def _check_gateway(
        self, results: Sequence[ProbeResult], now: datetime
    ) -> tuple[bool | None, list[EventAction]]:
        result = self._find(results, "ping", self.gateway) if self.gateway else None
        if result is None:
            return None, []

        evidence = {"gateway": self.gateway}
        if result.ok:
            self._gateway_fail = 0
            return True, self._close_event("gateway_down", evidence, now)

        self._gateway_fail += 1
        evidence["failures"] = self._gateway_fail
        if self._gateway_fail >= 3:
            return False, self._open_event("gateway_down", evidence, now)
        return False, []

    def _check_internet(
        self, results: Sequence[ProbeResult], now: datetime, gateway_ok: bool | None
    ) -> list[EventAction]:
        internet = [
            result
            for result in results
            if result.probe == "ping" and result.target in self.internet_targets
        ]
        if not internet:
            return []

        targets = [result.target for result in internet]
        all_fail = all(not result.ok for result in internet)
        if all_fail and gateway_ok is not False:
            self._internet_fail += 1
            evidence = {"targets": targets, "failures": self._internet_fail}
            if self._internet_fail >= 3:
                return self._open_event("internet_down", evidence, now)
            return []

        self._internet_fail = 0
        return self._close_event("internet_down", {"targets": targets}, now)

    def _check_dns(
        self, results: Sequence[ProbeResult], now: datetime
    ) -> list[EventAction]:
        dns = [result for result in results if result.probe == "dns"]
        if not dns:
            return []

        actions: list[EventAction] = []
        failed = [result.target for result in dns if not result.ok]
        if failed:
            self._dns_fail += 1
            if self._dns_fail >= 2:
                actions.extend(
                    self._open_event("dns_fail", {"resolvers": failed}, now)
                )
        else:
            self._dns_fail = 0
            actions.extend(
                self._close_event(
                    "dns_fail",
                    {"resolvers": [result.target for result in dns]},
                    now,
                )
            )

        slow = [
            result
            for result in dns
            if result.value is not None and result.value > 1000
        ]
        if slow:
            self._dns_slow += 1
            if self._dns_slow >= 3:
                actions.extend(
                    self._open_event(
                        "dns_slow",
                        {
                            "resolvers": [result.target for result in slow],
                            "latency_ms": max(
                                result.value for result in slow if result.value
                            ),
                        },
                        now,
                    )
                )
        else:
            self._dns_slow = 0
            actions.extend(
                self._close_event(
                    "dns_slow",
                    {"resolvers": [result.target for result in dns]},
                    now,
                )
            )
        return actions

    def _check_wifi(
        self, results: Sequence[ProbeResult], now: datetime
    ) -> list[EventAction]:
        if not self.wifi_monitored:
            return []

        state = self._find(results, "wifi", "state")
        signal = self._find(results, "wifi", "signal_pct")
        if state is None and signal is None:
            return []

        disconnected = (
            state is not None
            and state.text_value is not None
            and "disconnected" in state.text_value.lower()
        )
        weak_signal = (
            signal is not None
            and signal.value is not None
            and signal.value < 30
        )
        evidence = {
            "state": state.text_value if state else None,
            "signal_pct": signal.value if signal else None,
        }

        if disconnected or weak_signal:
            self._wifi_low += 1
            if self._wifi_low >= 2:
                return self._open_event("wifi_drop", evidence, now)
            return []

        self._wifi_low = 0
        return self._close_event("wifi_drop", evidence, now)

    def _check_latency(
        self, results: Sequence[ProbeResult], now: datetime
    ) -> list[EventAction]:
        values = [
            result.value
            for result in results
            if result.probe == "ping"
            and result.target in self.internet_targets
            and result.ok
            and result.value is not None
        ]
        if not values:
            return []

        current = max(values)
        self._latency_samples.append(current)
        if len(self._latency_samples) < self._latency_baseline_samples:
            return []

        baseline = median(self._latency_samples)
        evidence = {"current_ms": current, "baseline_ms": baseline}
        if baseline > 0 and current > 3 * baseline:
            return self._open_event("latency_spike", evidence, now)
        return self._close_event("latency_spike", evidence, now)

    def _check_packet_loss(
        self,
        packet_loss_pct: float | None,
        packet_loss_samples: int,
        now: datetime,
    ) -> list[EventAction]:
        if packet_loss_pct is None:
            return []

        evidence = {
            "loss_pct": packet_loss_pct,
            "samples": packet_loss_samples,
        }
        if packet_loss_samples >= 30 and packet_loss_pct > 5:
            return self._open_event("packet_loss", evidence, now)
        return self._close_event("packet_loss", evidence, now)

    def evaluate(
        self,
        results: Sequence[ProbeResult],
        now: datetime,
        *,
        packet_loss_pct: float | None = None,
        packet_loss_samples: int = 0,
    ) -> list[EventAction]:
        gateway_ok, actions = self._check_gateway(results, now)
        actions.extend(self._check_internet(results, now, gateway_ok))
        actions.extend(self._check_dns(results, now))
        actions.extend(self._check_wifi(results, now))
        actions.extend(self._check_latency(results, now))
        actions.extend(
            self._check_packet_loss(packet_loss_pct, packet_loss_samples, now)
        )
        return actions
