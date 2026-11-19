from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Sequence

import dns.exception
import dns.resolver

from blackbox.probe_types import ProbeResult


@dataclass(frozen=True)
class DnsAnswer:
    resolver: str
    rcode: str
    answers: list[str]
    latency_ms: float


ResolverFn = Callable[[str, str, float], DnsAnswer]


def _default_resolver(resolver: str, domain: str, timeout_s: float) -> DnsAnswer:
    start = time.perf_counter()
    client = dns.resolver.Resolver(configure=False)
    client.nameservers = [resolver]
    client.lifetime = timeout_s
    try:
        answer = client.resolve(domain, "A")
    except dns.resolver.NXDOMAIN:
        return DnsAnswer(resolver, "NXDOMAIN", [], (time.perf_counter() - start) * 1000)
    except dns.resolver.NoAnswer:
        return DnsAnswer(resolver, "NOERROR", [], (time.perf_counter() - start) * 1000)
    except dns.exception.Timeout as exc:
        raise TimeoutError("dns timeout") from exc
    latency_ms = (time.perf_counter() - start) * 1000
    addresses = [rdata.address for rdata in answer]
    return DnsAnswer(resolver, "NOERROR", addresses, latency_ms)


def probe_dns(
    resolvers: Sequence[str],
    *,
    domain: str = "example.com",
    resolver_fn: ResolverFn | None = None,
    timeout_s: float = 3.0,
) -> list[ProbeResult]:
    resolve = resolver_fn or _default_resolver
    results: list[ProbeResult] = []
    for resolver in resolvers:
        try:
            answer = resolve(resolver, domain, timeout_s)
        except TimeoutError:
            results.append(
                ProbeResult(
                    probe="dns",
                    target=resolver,
                    ok=False,
                    error_kind="timeout",
                    detail={"resolver": resolver},
                )
            )
            continue
        except dns.exception.DNSException as exc:
            results.append(
                ProbeResult(
                    probe="dns",
                    target=resolver,
                    ok=False,
                    error_kind="network",
                    detail={"resolver": resolver, "error": type(exc).__name__},
                )
            )
            continue
        except (OSError, ValueError):
            results.append(
                ProbeResult(
                    probe="dns",
                    target=resolver,
                    ok=False,
                    error_kind="network",
                    detail={"resolver": resolver},
                )
            )
            continue
        except Exception:
            results.append(
                ProbeResult(
                    probe="dns",
                    target=resolver,
                    ok=False,
                    error_kind="probe_error",
                    detail={"resolver": resolver},
                )
            )
            continue

        ok = answer.rcode == "NOERROR" and bool(answer.answers)
        results.append(
            ProbeResult(
                probe="dns",
                target=resolver,
                value=round(answer.latency_ms, 2),
                unit="ms",
                ok=ok,
                detail={
                    "rcode": answer.rcode,
                    "answers": answer.answers,
                    "resolver": resolver,
                },
                error_kind=None if ok else "network",
            )
        )
    return results
