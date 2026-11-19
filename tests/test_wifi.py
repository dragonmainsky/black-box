from pathlib import Path

from blackbox.probes.wifi import parse_netsh_wifi, probe_wifi

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_english():
    info = parse_netsh_wifi((FIXTURES / "netsh_wifi_en.txt").read_text(encoding="utf-8"))
    assert info.ssid == "HomeNet"
    assert info.signal_pct == 82.0
    assert info.rx_mbps == 866.7


def test_parse_thai():
    info = parse_netsh_wifi((FIXTURES / "netsh_wifi_th.txt").read_text(encoding="utf-8"))
    assert info.ssid == "HomeNet"
    assert info.signal_pct == 74.0


def test_parse_disconnected_keeps_state():
    info = parse_netsh_wifi(
        (FIXTURES / "netsh_wifi_disconnected.txt").read_text(encoding="utf-8")
    )
    assert info.state.lower().startswith("disconnected")
    assert info.ssid is None


def test_probe_returns_field_rows():
    output = (FIXTURES / "netsh_wifi_en.txt").read_text(encoding="utf-8")
    results = probe_wifi(run_fn=lambda: (0, output, ""))
    targets = {r.target for r in results}
    assert {"state", "ssid", "bssid", "signal_pct", "rx_mbps", "tx_mbps", "band"} <= targets


def test_probe_missing_adapter_is_probe_error():
    results = probe_wifi(run_fn=lambda: (1, "", "no wireless interface"))
    assert len(results) == 1
    assert results[0].ok is False
    assert results[0].error_kind == "probe_error"
