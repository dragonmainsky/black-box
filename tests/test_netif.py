import json
from pathlib import Path

from blackbox.probes.netif import parse_dns_json, parse_route_json

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_route_picks_lowest_effective_metric():
    info = parse_route_json((FIXTURES / "route.json").read_text(encoding="utf-8"))
    assert info.alias == "Ethernet"
    assert info.gateway == "192.168.1.1"
    assert info.is_wifi is False


def test_parse_route_keeps_metric_zero():
    raw = json.dumps(
        [
            {
                "InterfaceAlias": "Slow",
                "NextHop": "192.168.1.1",
                "RouteMetric": 0,
                "InterfaceMetric": 100,
            },
            {
                "InterfaceAlias": "Fast",
                "NextHop": "192.168.1.1",
                "RouteMetric": 0,
                "InterfaceMetric": 10,
            },
        ]
    )
    assert parse_route_json(raw).alias == "Fast"


def test_parse_route_ignores_onlink_vpn():
    raw = json.dumps(
        [
            {
                "InterfaceAlias": "VPN",
                "NextHop": "0.0.0.0",
                "RouteMetric": 0,
                "InterfaceMetric": 1,
            }
        ]
    )
    assert parse_route_json(raw) is None


def test_parse_dns_servers_by_alias():
    servers = parse_dns_json(
        (FIXTURES / "dns_servers.json").read_text(encoding="utf-8"), "Ethernet"
    )
    assert servers == ["192.168.1.1", "1.1.1.1"]
