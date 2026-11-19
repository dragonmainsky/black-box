from __future__ import annotations

from typing import Sequence

from blackbox.events.narrator import narrate_event


def summarize_events(events: Sequence[dict]) -> str:
    if not events:
        return "ไม่พบเหตุการณ์ในช่วงนี้"

    lines = [f"พบ {len(events)} เหตุการณ์"]
    for event in events[:10]:
        lines.append("- " + narrate_event(event))
    remaining = len(events) - 10
    if remaining > 0:
        lines.append(f"- ... อีก {remaining} เหตุการณ์")
    return "\n".join(lines)
