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
        self._open = set(open_types)
        self._latency_baseline_samples = max(2, latency_baseline_samples)
        self._gateway_fail = 0
        self._internet_fail = 0
        self._dns_fail = 0
        self._dns_slow = 0
        self._wifi_low = 0
        self._latency_samples: list[float] = []

    @staticmethod
    def _find(
        results: Sequence[ProbeResult], probe: str, target: str
    ) -> ProbeResult | None:
        return next(
            (
                result
                for result in results
                if result.probe == probe and result.target == target
            ),
            None,
        )

    def _open_action(
        self, event_type: str, evidence: dict[str, Any], ts: datetime
    ) -> EventAction | None:
        if event_type in self._open:
            return None
        severity, title, details = _RULES[event_type]
        self._open.add(event_type)
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
        if event_type not in self._open:
            return None
        severity, title, details = _RULES[event_type]
        self._open.discard(event_type)
        return EventAction(
            action="close",
            type=event_type,
            severity=severity,
            title=title,
            details=details,
            evidence={"recovered": True, **evidence},
            ts=ts,
        )

    def evaluate(
        self,
        results: Sequence[ProbeResult],
        now: datetime,
        *,
        packet_loss_pct: float | None = None,
        packet_loss_samples: int = 0,
    ) -> list[EventAction]:
        actions: list[EventAction] = []

        gateway_result = (
            self._find(results, "ping", self.gateway) if self.gateway else None
        )
        gateway_ok: bool | None = None
        if gateway_result is not None:
            if gateway_result.ok:
                gateway_ok = True
                self._gateway_fail = 0
                action = self._close_action(
                    "gateway_down", {"gateway": self.gateway}, now
                )
                if action:
                    actions.append(action)
            else:
                gateway_ok = False
                self._gateway_fail += 1
                if self._gateway_fail >= 3:
                    action = self._open_action(
                        "gateway_down",
                        {
                            "gateway": self.gateway,
                            "failures": self._gateway_fail,
                        },
                        now,
                    )
                    if action:
                        actions.append(action)

        internet_results = [
            result
            for result in results
            if result.probe == "ping" and result.target in self.internet_targets
        ]
        if internet_results:
            all_fail = all(not result.ok for result in internet_results)
            if all_fail and gateway_ok is not False:
                self._internet_fail += 1
                if self._internet_fail >= 3:
                    action = self._open_action(
                        "internet_down",
                        {
                            "targets": [
                                result.target for result in internet_results
                            ],
                            "failures": self._internet_fail,
                        },
                        now,
                    )
                    if action:
                        actions.append(action)
            else:
                self._internet_fail = 0
                action = self._close_action(
                    "internet_down",
                    {"targets": [result.target for result in internet_results]},
                    now,
                )
                if action:
                    actions.append(action)

        dns_results = [result for result in results if result.probe == "dns"]
        if dns_results:
            any_fail = any(not result.ok for result in dns_results)
            if any_fail:
                self._dns_fail += 1
                if self._dns_fail >= 2:
                    action = self._open_action(
                        "dns_fail",
                        {
                            "resolvers": [
                                result.target
                                for result in dns_results
                                if not result.ok
                            ]
                        },
                        now,
                    )
                    if action:
                        actions.append(action)
            else:
                self._dns_fail = 0
                action = self._close_action(
                    "dns_fail",
                    {"resolvers": [result.target for result in dns_results]},
                    now,
                )
                if action:
                    actions.append(action)

            slow = [
                result
                for result in dns_results
                if result.value is not None and result.value > 1000
            ]
            if slow:
                self._dns_slow += 1
                if self._dns_slow >= 3:
                    action = self._open_action(
                        "dns_slow",
                        {
                            "resolvers": [result.target for result in slow],
                            "latency_ms": max(
                                result.value for result in slow if result.value
                            ),
                        },
                        now,
                    )
                    if action:
                        actions.append(action)
            else:
                self._dns_slow = 0
                action = self._close_action(
                    "dns_slow",
                    {"resolvers": [result.target for result in dns_results]},
                    now,
                )
                if action:
                    actions.append(action)

        if self.wifi_monitored:
            state = self._find(results, "wifi", "state")
            signal = self._find(results, "wifi", "signal_pct")
            if state is not None or signal is not None:
                low = (
                    state is not None
                    and state.text_value is not None
                    and "disconnected" in state.text_value.lower()
                ) or (
                    signal is not None
                    and signal.value is not None
                    and signal.value < 30
                )
                if low:
                    self._wifi_low += 1
                    if self._wifi_low >= 2:
                        action = self._open_action(
                            "wifi_drop",
                            {
                                "state": state.text_value if state else None,
                                "signal_pct": signal.value if signal else None,
                            },
                            now,
                        )
                        if action:
                            actions.append(action)
                else:
                    self._wifi_low = 0
                    action = self._close_action(
                        "wifi_drop",
                        {
                            "state": state.text_value if state else None,
                            "signal_pct": signal.value if signal else None,
                        },
                        now,
                    )
                    if action:
                        actions.append(action)

        latency_values = [
            result.value
            for result in results
            if result.probe == "ping"
            and result.target in self.internet_targets
            and result.ok
            and result.value is not None
        ]
        if latency_values:
            current = max(latency_values)
            self._latency_samples.append(current)
            if len(self._latency_samples) >= self._latency_baseline_samples:
                baseline = median(self._latency_samples)
                if baseline > 0 and current > 3 * baseline:
                    action = self._open_action(
                        "latency_spike",
                        {"current_ms": current, "baseline_ms": baseline},
                        now,
                    )
                    if action:
                        actions.append(action)
                else:
                    action = self._close_action(
                        "latency_spike",
                        {"current_ms": current, "baseline_ms": baseline},
                        now,
                    )
                    if action:
                        actions.append(action)

        if packet_loss_pct is not None:
            evidence = {
                "loss_pct": packet_loss_pct,
                "samples": packet_loss_samples,
            }
            if packet_loss_samples >= 30 and packet_loss_pct > 5:
                action = self._open_action("packet_loss", evidence, now)
                if action:
                    actions.append(action)
            else:
                action = self._close_action("packet_loss", evidence, now)
                if action:
                    actions.append(action)

        return actions
