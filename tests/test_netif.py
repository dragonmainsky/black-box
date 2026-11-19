from pathlib import Path

from blackbox.probes.netif import parse_dns_json, parse_route_json

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_route_picks_lowest_metric():
    info = parse_route_json((FIXTURES / "route.json").read_text(encoding="utf-8"))
    assert info.alias == "Ethernet"
    assert info.gateway == "192.168.1.1"
    assert info.is_wifi is False


def test_parse_dns_servers_by_alias():
    servers = parse_dns_json(
        (FIXTURES / "dns_servers.json").read_text(encoding="utf-8"), "Ethernet"
    )
    assert servers == ["192.168.1.1", "1.1.1.1"]
