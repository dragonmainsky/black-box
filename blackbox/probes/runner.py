from __future__ import annotations

import sys
import time
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Callable

from sqlalchemy import select
from sqlalchemy.engine import Engine

from blackbox.config import Config
from blackbox.events.gap import record_gap_if_needed
from blackbox.events.rules import EventAction, RuleEngine
from blackbox.probe_types import ProbeResult
from blackbox.probes.arp import probe_arp
from blackbox.probes.dns import ResolverFn, probe_dns
from blackbox.probes.netif import InterfaceInfo, detect_dns_servers, detect_interface
from blackbox.probes.ping import EchoSender, WindowsEchoSender, ping_targets
from blackbox.probes.public_ip import probe_public_ip
from blackbox.probes.wifi import RunFn, probe_wifi
from blackbox.store.devices import upsert_devices
from blackbox.store.events import (
    apply_actions,
    open_event,
    open_event_types,
    recent_events as store_recent_events,
)
from blackbox.store.meta import meta_get, meta_set
from blackbox.store.probes import insert_probes, ping_window_loss
from blackbox.store.retention import run_maintenance
from blackbox.store.tables import probes


def summarize_cycle(results: list[ProbeResult]) -> str:
    counts: dict[str, int] = {}
    for result in results:
        counts[result.probe] = counts.get(result.probe, 0) + 1
    parts = [f"{name} {count}" for name, count in counts.items()]
    text = ", ".join(parts) if parts else "ไม่มี probe"
    failures = [result for result in results if not result.ok]
    if failures:
        labels = ", ".join(
            f"{result.target or result.probe}({result.error_kind or 'fail'})"
            for result in failures[:3]
        )
        text += f" | fail {len(failures)}: {labels}"
    return text


class ProbeRunner:
    def __init__(
        self,
        engine: Engine,
        config: Config,
        *,
        interface_fn: Callable[[], InterfaceInfo | None] | None = None,
        dns_servers_fn: Callable[[str], list[str]] | None = None,
        ping_sender: EchoSender | None = None,
        dns_resolver_fn: ResolverFn | None = None,
        wifi_run_fn: RunFn | None = None,
        arp_run_fn: RunFn | None = None,
        public_ip_fn: Callable[[], ProbeResult] | None = None,
        on_event: Callable[[EventAction], None] | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        self.engine = engine
        self.config = config
        self.interface_fn = interface_fn or detect_interface
        self.dns_servers_fn = dns_servers_fn or detect_dns_servers
        self.ping_sender = ping_sender
        self.dns_resolver_fn = dns_resolver_fn
        self.wifi_run_fn = wifi_run_fn
        self.arp_run_fn = arp_run_fn
        self.public_ip_fn = public_ip_fn
        self.on_event = on_event
        self.sleep_fn = sleep_fn
        self._interface: InterfaceInfo | None = None
        self._interface_checked_at: datetime | None = None
        self._last_run: dict[str, datetime] = {}
        self._rules: RuleEngine | None = None

    def _get_interface(
        self, now: datetime, *, force_refresh: bool = False
    ) -> InterfaceInfo | None:
        if (
            force_refresh
            or self._interface_checked_at is None
            or (now - self._interface_checked_at).total_seconds() >= 300
        ):
            self._interface = self.interface_fn()
            self._interface_checked_at = now
        return self._interface

    def _check_interface_change(
        self, info: InterfaceInfo | None, now: datetime
    ) -> None:
        if info is None:
            return
        last_alias = meta_get(self.engine, "last_interface")
        last_gw = meta_get(self.engine, "last_gateway")

        if last_alias is None:
            with self.engine.connect() as conn:
                row = conn.execute(
                    select(probes.c.interface)
                    .where(probes.c.interface.is_not(None))
                    .order_by(probes.c.id.desc())
                    .limit(1)
                ).first()
                if row and row[0]:
                    last_alias = row[0]

        if last_alias is not None:
            gw_changed = last_gw is not None and last_gw != (info.gateway or "")
            if last_alias != info.alias or gw_changed:
                open_event(
                    self.engine,
                    event_type="interface_change",
                    severity="low",
                    title="เปลี่ยนอินเทอร์เฟซ",
                    details=f"เปลี่ยนจาก {last_alias} เป็น {info.alias}",
                    evidence={
                        "old_interface": last_alias,
                        "new_interface": info.alias,
                        "old_gateway": last_gw,
                        "new_gateway": info.gateway,
                    },
                    ts=now,
                )

        if last_alias != info.alias:
            meta_set(self.engine, "last_interface", info.alias)
        if last_gw != (info.gateway or ""):
            meta_set(self.engine, "last_gateway", info.gateway or "")

    def _sender(self) -> EchoSender:
        if self.ping_sender is None:
            self.ping_sender = WindowsEchoSender()
        return self.ping_sender

    def update_config(self, config: Config) -> None:
        """ใช้ค่ารอบถัดไปโดยไม่ต้องรีสตาร์ท process"""
        self.config = config

    def _ensure_rules(self, info: InterfaceInfo | None) -> RuleEngine:
        gateway = info.gateway if info else None
        wifi = bool(info and info.is_wifi)
        if (
            self._rules is None
            or self._rules.gateway != gateway
            or self._rules.wifi_monitored != wifi
        ):
            self._rules = RuleEngine(
                gateway=gateway,
                internet_targets=self.config.targets,
                wifi_monitored=wifi,
                open_types=open_event_types(self.engine),
            )
        return self._rules

    def _stamp(self, results: list[ProbeResult], info: InterfaceInfo | None) -> list[ProbeResult]:
        if info is None:
            return results
        return [replace(result, interface=info.alias) for result in results]

    def run_once(self, now: datetime | None = None) -> list[ProbeResult]:
        return self._run(
            now or datetime.now(timezone.utc),
            force_all=True,
            update_last_cycle=False,
        )

    def run_cycle(self, now: datetime) -> list[ProbeResult]:
        last = meta_get(self.engine, "last_cycle")
        if last:
            record_gap_if_needed(
                self.engine,
                datetime.fromisoformat(last),
                now,
                self.config.base_interval_s,
            )
        return self._run(now, force_all=False, update_last_cycle=True)

    def _run(
        self, now: datetime, *, force_all: bool, update_last_cycle: bool
    ) -> list[ProbeResult]:
        info = self._get_interface(now, force_refresh=force_all)
        self._check_interface_change(info, now)
        alias = info.alias if info else None
        rules = self._ensure_rules(info)
        results: list[ProbeResult] = []
        if update_last_cycle:
            meta_set(self.engine, "last_cycle", now.isoformat())

        def due(key: str, interval_s: int) -> bool:
            if force_all or key not in self._last_run:
                return True
            return (now - self._last_run[key]).total_seconds() >= interval_s

        if due("ping", self.config.base_interval_s):
            targets: list[str] = []
            if info and info.gateway:
                targets.append(info.gateway)
            targets.extend(self.config.targets)
            targets = list(dict.fromkeys(targets))
            try:
                results.extend(
                    ping_targets(
                        targets,
                        self._sender(),
                        interface=alias,
                        echo_count=self.config.echo_count,
                        timeout_ms=self.config.echo_timeout_ms,
                    )
                )
            except Exception:
                results.extend(
                    ProbeResult(
                        probe="ping",
                        target=target,
                        ok=False,
                        interface=alias,
                        error_kind="probe_error",
                    )
                    for target in targets
                )
            self._last_run["ping"] = now

        if due("dns", self.config.dns_interval_s):
            resolvers: list[str] = []
            if info:
                resolvers.extend(self.dns_servers_fn(info.alias) or [])
            resolvers.extend(self.config.targets)
            resolvers = list(dict.fromkeys(resolvers))
            results.extend(
                probe_dns(resolvers, resolver_fn=self.dns_resolver_fn)
            )
            self._last_run["dns"] = now

        if info and info.is_wifi and due("wifi", self.config.wifi_interval_s):
            results.extend(probe_wifi(self.wifi_run_fn, interface=alias))
            self._last_run["wifi"] = now

        if due("arp", self.config.arp_interval_s):
            sweep = probe_arp(self.arp_run_fn, interface=alias)
            results.append(sweep.result)
            new_macs = upsert_devices(self.engine, sweep.entries, now)
            if new_macs:
                entry_map = {
                    e.mac.lower().replace(":", "-"): e for e in sweep.entries
                }
                for mac in new_macs:
                    entry = entry_map.get(mac)
                    ip = entry.ip if entry else None
                    evidence = {"mac": mac}
                    if ip:
                        evidence["ip"] = ip
                    open_event(
                        self.engine,
                        event_type="new_device",
                        severity="low",
                        title="พบอุปกรณ์ใหม่",
                        details=f"พบ MAC {mac}" + (f" ({ip})" if ip else ""),
                        evidence=evidence,
                        ts=now,
                    )
            self._last_run["arp"] = now

        if self.config.public_ip_enabled and due(
            "public_ip", self.config.public_ip_interval_s
        ):
            result = (
                self.public_ip_fn() if self.public_ip_fn else probe_public_ip()
            )
            results.append(result)
            if result.ok and result.text_value:
                current_ip = result.text_value
                last_ip = meta_get(self.engine, "last_public_ip")
                if last_ip and last_ip != current_ip:
                    open_event(
                        self.engine,
                        event_type="public_ip_change",
                        severity="low",
                        title="Public IP เปลี่ยน",
                        details=f"Public IP เปลี่ยนจาก {last_ip} เป็น {current_ip}",
                        evidence={"old_ip": last_ip, "new_ip": current_ip},
                        ts=now,
                    )
                if last_ip != current_ip:
                    meta_set(self.engine, "last_public_ip", current_ip)
            self._last_run["public_ip"] = now

        results = self._stamp(results, info)
        insert_probes(self.engine, results, now)
        window = ping_window_loss(
            self.engine, self.config.targets, now - timedelta(minutes=5)
        )
        actions = rules.evaluate(
            results,
            now,
            packet_loss_pct=window.loss_pct,
            packet_loss_samples=window.sent,
        )
        if actions:
            apply_actions(self.engine, actions)
            if self.on_event:
                for action in actions:
                    try:
                        self.on_event(action)
                    except Exception:
                        pass
        return results

    def _maybe_maintenance(self, now: datetime):
        last = meta_get(self.engine, "last_maintenance")
        if last and (
            now - datetime.fromisoformat(last)
        ).total_seconds() < self.config.maintenance_interval_s:
            return None
        return run_maintenance(
            self.engine,
            now,
            retention_days=self.config.retention_days,
            rollup_days=self.config.rollup_retention_days,
        )

    def run_forever(self) -> None:
        database = self.engine.url.database or "(unknown)"
        print(
            f"เริ่มเฝ้าระวัง — ทุก {self.config.base_interval_s} วินาที",
            flush=True,
        )
        print(f"ฐานข้อมูล: {database}", flush=True)
        print("กด Ctrl+C เพื่อหยุด", flush=True)
        next_at = time.monotonic()
        while True:
            next_at = max(next_at, time.monotonic())
            now = datetime.now(timezone.utc)
            try:
                self._maybe_maintenance(now)
            except Exception as exc:
                print(f"maintenance error: {exc}", file=sys.stderr, flush=True)
            try:
                results = self.run_cycle(now)
                stamp = now.astimezone().strftime("%H:%M:%S")
                print(f"[{stamp}] {summarize_cycle(results)}", flush=True)
            except Exception as exc:
                print(f"probe cycle error: {exc}", file=sys.stderr, flush=True)
            next_at += self.config.base_interval_s
            delay = next_at - time.monotonic()
            if delay < 0:
                missed = int((-delay) // self.config.base_interval_s) + 1
                next_at += missed * self.config.base_interval_s
                delay = next_at - time.monotonic()
            self.sleep_fn(max(0.0, delay))

    def recent_events(self, limit: int = 50) -> list[dict]:
        return store_recent_events(self.engine, limit)
