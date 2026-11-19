from blackbox.probes.dns import DnsAnswer, probe_dns

import dns.resolver


def test_dns_success():
    def resolver(resolver, domain, timeout_s):
        return DnsAnswer(resolver, "NOERROR", ["93.184.216.34"], 8.0)

    [result] = probe_dns(["1.1.1.1"], resolver_fn=resolver)
    assert result.ok is True
    assert result.value == 8.0
    assert result.detail["rcode"] == "NOERROR"


def test_dns_nxdomain_is_network_error():
    def resolver(resolver, domain, timeout_s):
        return DnsAnswer(resolver, "NXDOMAIN", [], 12.0)

    [result] = probe_dns(["1.1.1.1"], resolver_fn=resolver)
    assert result.ok is False
    assert result.error_kind == "network"


def test_dns_timeout_is_timeout_error():
    def resolver(resolver, domain, timeout_s):
        raise TimeoutError("dns timeout")

    [result] = probe_dns(["1.1.1.1"], resolver_fn=resolver)
    assert result.ok is False
    assert result.error_kind == "timeout"


def test_dns_one_row_per_resolver():
    def resolver(resolver, domain, timeout_s):
        return DnsAnswer(resolver, "NOERROR", ["1.2.3.4"], 5.0)

    results = probe_dns(["1.1.1.1", "8.8.8.8"], resolver_fn=resolver)
    assert len(results) == 2
    assert {r.target for r in results} == {"1.1.1.1", "8.8.8.8"}


def test_dns_no_nameservers_is_network_error():
    def resolver(resolver, domain, timeout_s):
        raise dns.resolver.NoNameservers()

    [result] = probe_dns(["1.1.1.1"], resolver_fn=resolver)
    assert result.ok is False
    assert result.error_kind == "network"
