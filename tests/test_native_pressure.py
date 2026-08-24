from __future__ import annotations

from pathlib import Path

import pytest

from elasticuma.native_pressure import load_pressure_events


def test_native_pressure_parser_accepts_ordered_kernel_events(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    path.write_text(
        '{"schemaVersion":1,"kind":"start","monotonicNanoseconds":10}\n'
        '{"schemaVersion":1,"kind":"pressure","level":"warning",'
        '"monotonicNanoseconds":20}\n',
        encoding="utf-8",
    )
    events = load_pressure_events(path)
    assert [event["kind"] for event in events] == ["start", "pressure"]


def test_native_pressure_parser_fails_closed_on_missing_start(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    path.write_text(
        '{"schemaVersion":1,"kind":"pressure","level":"normal","monotonicNanoseconds":20}\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="begin"):
        load_pressure_events(path)
