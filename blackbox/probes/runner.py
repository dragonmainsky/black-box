from __future__ import annotations

import sys
import time
from dataclasses import replace
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy.engine import Engine

from blackbox.config import Config
from blackbox.events.gap import record_gap_if_needed
from blackbox.probe_types import ProbeResult
from blackbox.probes.arp import probe_arp
from blackbox.probes.dns import ResolverFn, probe_dns
from blackbox.probes.netif import InterfaceInfo, detect_dns_servers, detect_interface
from blackbox.probes.ping import EchoSender, WindowsEchoSender, ping_targets
from blackbox.probes.public_ip import probe_public_ip
from blackbox.probes.wifi import RunFn, probe_wifi
from blackbox.store.devices import upsert_devices
from blackbox.store.events import recent_events as store_recent_events
from blackbox.store.meta import meta_get, meta_set
from blackbox.store.probes import insert_probes
from blackbox.store.retention import run_maintenance


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
        self.sleep_fn = sleep_fn
        self._interface: InterfaceInfo | None = None
        self._interface_checked_at: datetime | None = None
        self._last_run: dict[str, datetime] = {}

    def _get_interface(self, now: datetime) -> InterfaceInfo | None:
        if (
            self._interface_checked_at is None
            or (now - self._interface_checked_at).total_seconds() >= 300
        ):
            self._interface = self.interface_fn()
            self._interface_checked_at = now
        return self._interface

    def _sender(self) -> EchoSender:
        if self.ping_sender is None:
            self.ping_sender = WindowsEchoSender()
        return self.ping_sender

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
        info = self._get_interface(now)
        alias = info.alias if info else None
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
            upsert_devices(self.engine, sweep.entries, now)
            self._last_run["arp"] = now

        if self.config.public_ip_enabled and due(
            "public_ip", self.config.public_ip_interval_s
        ):
            result = (
                self.public_ip_fn() if self.public_ip_fn else probe_public_ip()
            )
            results.append(result)
            self._last_run["public_ip"] = now

        results = self._stamp(results, info)
        insert_probes(self.engine, results, now)
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
