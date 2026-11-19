from blackbox.probes.ping import ping_targets


class FakeSender:
    def __init__(self, replies):
        self.replies = list(replies)

    def send(self, target, timeout_ms):
        return self.replies.pop(0)


def test_ping_aggregates_three_echoes():
    sender = FakeSender([10.0, 20.0, 30.0])
    [result] = ping_targets(["1.1.1.1"], sender, echo_count=3)
    assert result.ok is True
    assert result.value == 20.0
    assert result.detail["sent"] == 3
    assert result.detail["recv"] == 3
    assert result.detail["loss_pct"] == 0.0


def test_ping_marks_partial_loss():
    sender = FakeSender([10.0, None, 30.0])
    [result] = ping_targets(["1.1.1.1"], sender, echo_count=3)
    assert result.ok is True
    assert result.detail["recv"] == 2
    assert result.detail["loss_pct"] == 33.3


def test_ping_all_fail_is_network_error():
    sender = FakeSender([None, None, None])
    [result] = ping_targets(["1.1.1.1"], sender, echo_count=3)
    assert result.ok is False
    assert result.error_kind == "network"


def test_ping_sender_exception_is_probe_error():
    class Broken:
        def send(self, target, timeout_ms):
            raise OSError("icmp unavailable")

    [result] = ping_targets(["1.1.1.1"], Broken(), echo_count=1)
    assert result.ok is False
    assert result.error_kind == "probe_error"
