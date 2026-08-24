from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def monitor_binary(project_root: Path) -> Path:
    return project_root / "native/.build/release/elasticuma-pressure-monitor"


def load_pressure_events(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid pressure JSONL at line {line_number}") from exc
            if not isinstance(event, dict):
                raise ValueError(f"pressure event {line_number} is not an object")
            if event.get("schemaVersion") != 1:
                raise ValueError(f"pressure event {line_number} has an unsupported schema")
            kind = event.get("kind")
            if kind not in {"start", "pressure"}:
                raise ValueError(f"pressure event {line_number} has invalid kind {kind!r}")
            if kind == "pressure" and event.get("level") not in {
                "normal",
                "warning",
                "critical",
                "unknown",
            }:
                raise ValueError(f"pressure event {line_number} has invalid level")
            monotonic = event.get("monotonicNanoseconds")
            if isinstance(monotonic, bool) or not isinstance(monotonic, int) or monotonic <= 0:
                raise ValueError(f"pressure event {line_number} lacks monotonic time")
            events.append(event)
    if not events or events[0].get("kind") != "start":
        raise ValueError("pressure stream must begin with one start event")
    if sum(event.get("kind") == "start" for event in events) != 1:
        raise ValueError("pressure stream must contain exactly one start event")
    times = [int(event["monotonicNanoseconds"]) for event in events]
    if times != sorted(times):
        raise ValueError("pressure events are not monotonic")
    return events
