from blackbox.probes.public_ip import probe_public_ip


def test_public_ip_success():
    result = probe_public_ip(fetch_fn=lambda: "203.0.113.7")
    assert result.ok is True
    assert result.text_value == "203.0.113.7"


def test_public_ip_invalid_response():
    result = probe_public_ip(fetch_fn=lambda: "not-an-ip")
    assert result.ok is False
    assert result.error_kind == "parse_error"


def test_public_ip_network_error():
    def broken():
        raise OSError("offline")

    result = probe_public_ip(fetch_fn=broken)
    assert result.ok is False
    assert result.error_kind == "network"
