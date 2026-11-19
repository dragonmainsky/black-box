from __future__ import annotations

import json
from typing import Any, Sequence

from blackbox.events.rules import EventAction


def _extract_data(
    event: dict[str, Any] | EventAction,
) -> tuple[str, dict[str, Any], bool, str, str]:
    if isinstance(event, EventAction):
        event_type = event.type
        evidence = event.evidence or {}
        is_recovered = event.action == "close" or bool(evidence.get("recovered"))
        title = event.title
        details = event.details
    else:
        event_type = event.get("type", "")
        raw_evidence = event.get("evidence")
        if isinstance(raw_evidence, str):
            try:
                evidence = json.loads(raw_evidence)
            except (ValueError, TypeError):
                evidence = {}
        elif isinstance(raw_evidence, dict):
            evidence = raw_evidence
        else:
            evidence = {}
        is_recovered = bool(event.get("ts_end")) or bool(evidence.get("recovered"))
        title = event.get("title", "")
        details = event.get("details", "")
    return event_type, evidence, is_recovered, title, details


def narrate_event(event: dict[str, Any] | EventAction) -> str:
    event_type, evidence, is_recovered, title, details = _extract_data(event)

    if event_type == "gateway_down":
        gw = evidence.get("gateway")
        gw_str = f" (gateway {gw})" if gw else ""
        if is_recovered:
            return f"เราเตอร์{gw_str} กลับมาตอบสนองตามปกติแล้ว"
        failures = evidence.get("failures")
        fail_str = f" ติดต่อกัน {failures} ครั้ง" if failures else ""
        return f"เราเตอร์{gw_str} ไม่ตอบสนอง ping{fail_str}"

    if event_type == "internet_down":
        if is_recovered:
            return "การเชื่อมต่ออินเทอร์เน็ตกลับมาใช้งานได้ตามปกติแล้ว"
        targets = evidence.get("targets")
        target_str = f" ไม่สามารถติดต่อ {', '.join(targets)} ได้" if targets else ""
        return f"อินเทอร์เน็ตหลุด{target_str} แต่เราเตอร์ยังทำงานปกติ"

    if event_type == "dns_fail":
        if is_recovered:
            return "ระบบ DNS กลับมาทำงานได้ตามปกติแล้ว"
        resolvers = evidence.get("resolvers")
        res_str = f" ({', '.join(resolvers)})" if resolvers else ""
        return f"ระบบ DNS ล่ม resolver{res_str} ไม่ตอบสนอง"

    if event_type == "dns_slow":
        if is_recovered:
            return "ความเร็วการตอบสนองของ DNS กลับสู่ระดับปกติแล้ว"
        latency = evidence.get("latency_ms")
        resolvers = evidence.get("resolvers")
        lat_str = f" ({latency:.0f} ms)" if latency is not None else ""
        res_str = f" ผ่าน {', '.join(resolvers)}" if resolvers else ""
        return f"DNS ตอบสนองช้า{lat_str}{res_str}"

    if event_type == "wifi_drop":
        if is_recovered:
            return "สัญญาณ Wi-Fi กลับมาเชื่อมต่อตามปกติแล้ว"
        state = evidence.get("state")
        signal = evidence.get("signal_pct")
        if state and "disconnected" in state.lower():
            return "การเชื่อมต่อ Wi-Fi หลุด"
        if signal is not None:
            return f"สัญญาณ Wi-Fi อ่อนลงเหลือ {signal:.0f}%"
        return "สัญญาณ Wi-Fi หลุดหรืออ่อนผิดปกติ"

    if event_type == "latency_spike":
        if is_recovered:
            return "ค่า latency อินเทอร์เน็ตกลับสู่ระดับปกติแล้ว"
        cur = evidence.get("current_ms")
        base = evidence.get("baseline_ms")
        cur_str = f"{cur:.1f} ms" if cur is not None else "สูงผิดปกติ"
        base_str = f" (ปกติมัธยฐาน {base:.1f} ms)" if base is not None else ""
        return f"ค่า latency พุ่งสูงแตะ {cur_str}{base_str}"

    if event_type == "packet_loss":
        if is_recovered:
            return "อัตรา packet loss กลับสู่ระดับปกติแล้ว"
        loss = evidence.get("loss_pct")
        samples = evidence.get("samples")
        loss_str = f"{loss:.1f}%" if loss is not None else "สูง"
        sample_str = f" (จาก {samples} แพ็กเก็ต)" if samples else ""
        return f"พบ packet loss สูง {loss_str}{sample_str}"

    if event_type == "new_device":
        mac = evidence.get("mac", "")
        ip = evidence.get("ip")
        ip_str = f" (IP: {ip})" if ip else ""
        return f"พบอุปกรณ์ใหม่เชื่อมต่อเครือข่าย MAC {mac}{ip_str}"

    if event_type == "public_ip_change":
        old_ip = evidence.get("old_ip", "ไม่ระบุ")
        new_ip = evidence.get("new_ip", "ไม่ระบุ")
        return f"หมายเลข Public IP เปลี่ยนจาก {old_ip} เป็น {new_ip}"

    if event_type == "interface_change":
        old_if = evidence.get("old_interface", "ไม่ระบุ")
        new_if = evidence.get("new_interface", "ไม่ระบุ")
        return f"เปลี่ยนการเชื่อมต่อเครือข่ายจาก {old_if} เป็น {new_if}"

    if event_type == "monitor_gap":
        gap = evidence.get("gap_seconds", 0.0)
        return f"ระบบไม่ได้เก็บข้อมูลเป็นเวลา {gap:.0f} วินาที (อาจมีการปิดเครื่องหรือหลับ)"

    if title:
        return f"{title}: {details}" if details else title

    return f"เกิดเหตุการณ์ {event_type}"


def narrate_events(events: Sequence[dict[str, Any] | EventAction]) -> list[str]:
    return [narrate_event(e) for e in events]
