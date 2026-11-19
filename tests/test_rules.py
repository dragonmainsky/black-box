from datetime import datetime, timezone

from blackbox.events.rules import RuleEngine
from blackbox.probe_types import ProbeResult

NOW = datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)
GW = "192.168.1.1"
NET = ("1.1.1.1", "8.8.8.8")


def ping(target, ok, value=10.0):
    return ProbeResult(
        probe="ping",
        target=target,
        value=value if ok else None,
        unit="ms",
        ok=ok,
        detail={"loss_pct": 0.0 if ok else 100.0},
    )


def dns(target, ok, value=10.0):
    return ProbeResult(
        probe="dns",
        target=target,
        value=value,
        unit="ms",
        ok=ok,
        error_kind=None if ok else "network",
    )


def wifi(state="connected", signal=80.0):
    return [
        ProbeResult(probe="wifi", target="state", text_value=state, ok=True),
        ProbeResult(probe="wifi", target="signal_pct", value=signal, unit="%", ok=True),
    ]


def evaluate(engine, results, times=1):
    actions = []
    for _ in range(times):
        actions.extend(engine.evaluate(results, NOW))
    return actions


def test_gateway_down_opens_after_three_failures_and_closes():
    engine = RuleEngine(gateway=GW, internet_targets=("1.1.1.1",))
    fail = [ping(GW, False), ping("1.1.1.1", True)]
    assert evaluate(engine, fail, 2) == []
    actions = evaluate(engine, fail)
    assert [a.type for a in actions] == ["gateway_down"]
    assert actions[0].action == "open"

    actions = evaluate(engine, [ping(GW, True), ping("1.1.1.1", True)])
    assert [a.type for a in actions] == ["gateway_down"]
    assert actions[0].action == "close"


def test_internet_down_requires_gateway_ok_and_three_failures():
    engine = RuleEngine(gateway=GW, internet_targets=NET)
    fail = [ping(GW, True), ping("1.1.1.1", False), ping("8.8.8.8", False)]
    assert evaluate(engine, fail, 2) == []
    actions = evaluate(engine, fail)
    assert [a.type for a in actions] == ["internet_down"]


def test_internet_down_does_not_open_while_gateway_down():
    engine = RuleEngine(gateway=GW, internet_targets=NET)
    fail = [ping(GW, False), ping("1.1.1.1", False), ping("8.8.8.8", False)]
    actions = evaluate(engine, fail, 3)
    assert [a.type for a in actions] == ["gateway_down"]


def test_dns_fail_opens_after_two_failures_and_closes():
    engine = RuleEngine()
    fail = [dns("1.1.1.1", False), dns("8.8.8.8", True)]
    assert evaluate(engine, fail, 1) == []
    actions = evaluate(engine, fail)
    assert [a.type for a in actions] == ["dns_fail"]
    assert actions[0].action == "open"

    actions = evaluate(engine, [dns("1.1.1.1", True), dns("8.8.8.8", True)])
    assert [a.type for a in actions] == ["dns_fail"]
    assert actions[0].action == "close"


def test_dns_slow_opens_after_three_slow_results():
    engine = RuleEngine()
    slow = [dns("1.1.1.1", True, 1500.0), dns("8.8.8.8", True, 10.0)]
    assert evaluate(engine, slow, 2) == []
    actions = evaluate(engine, slow)
    assert [a.type for a in actions] == ["dns_slow"]


def test_wifi_drop_opens_after_two_low_signals():
    engine = RuleEngine(wifi_monitored=True)
    low = wifi("connected", 20.0)
    assert evaluate(engine, low, 1) == []
    actions = evaluate(engine, low)
    assert [a.type for a in actions] == ["wifi_drop"]
    assert actions[0].action == "open"


def test_wifi_rule_ignored_when_not_monitored():
    engine = RuleEngine(wifi_monitored=False)
    low = wifi("disconnected", 0.0)
    assert evaluate(engine, low, 3) == []


def test_latency_spike_after_baseline_and_close():
    engine = RuleEngine(
        internet_targets=("1.1.1.1",), latency_baseline_samples=10
    )
    for _ in range(10):
        assert evaluate(engine, [ping("1.1.1.1", True, 10.0)]) == []
    actions = evaluate(engine, [ping("1.1.1.1", True, 50.0)])
    assert [a.type for a in actions] == ["latency_spike"]
    assert actions[0].action == "open"

    actions = evaluate(engine, [ping("1.1.1.1", True, 10.0)])
    assert [a.type for a in actions] == ["latency_spike"]
    assert actions[0].action == "close"


def test_no_duplicate_open_event():
    engine = RuleEngine(gateway=GW, internet_targets=("1.1.1.1",))
    fail = [ping(GW, False)]
    evaluate(engine, fail, 3)
    assert evaluate(engine, fail) == []
