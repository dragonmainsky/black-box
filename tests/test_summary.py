from blackbox.summary import summarize_events


def test_summary_empty():
    assert summarize_events([]) == "ไม่พบเหตุการณ์ในช่วงนี้"


def test_summary_with_dns_event():
    events = [
        {
            "type": "dns_fail",
            "severity": "high",
            "ts_start": "2026-11-19T12:00:00+00:00",
            "ts_end": None,
            "evidence": {"resolvers": ["1.1.1.1"]},
            "title": "DNS ล่ม",
            "details": "",
        }
    ]
    text = summarize_events(events)
    assert "1 เหตุการณ์" in text
    assert "DNS" in text
    assert "1.1.1.1" in text
