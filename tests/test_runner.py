from __future__ import annotations

import signal
import subprocess
from pathlib import Path

from elasticuma import runner
from elasticuma.config import load_experiment
from elasticuma.schema import MemorySnapshot

ROOT = Path(__file__).resolve().parents[1]


class _FakeProcess:
    pid = 4242

    def __init__(self, *, times_out: bool) -> None:
        self.times_out = times_out
        self.waits = 0

    def poll(self) -> None:
        return None

    def wait(self, timeout: float) -> int:
        del timeout
        self.waits += 1
        if self.times_out and self.waits == 1:
            raise subprocess.TimeoutExpired("fake", 1)
        return 0


def test_terminate_signals_entire_session(monkeypatch) -> None:
    calls: list[tuple[int, signal.Signals]] = []
    monkeypatch.setattr(runner.os, "killpg", lambda pid, sig: calls.append((pid, sig)))
    process = _FakeProcess(times_out=False)
    runner._terminate(process)  # type: ignore[arg-type]
    assert calls == [(4242, signal.SIGTERM)]


def test_terminate_escalates_entire_session(monkeypatch) -> None:
    calls: list[tuple[int, signal.Signals]] = []
    monkeypatch.setattr(runner.os, "killpg", lambda pid, sig: calls.append((pid, sig)))
    process = _FakeProcess(times_out=True)
    runner._terminate(process)  # type: ignore[arg-type]
    assert calls == [(4242, signal.SIGTERM), (4242, signal.SIGKILL)]


def test_recovery_gate_requires_consecutive_normal_samples(monkeypatch) -> None:
    spec = load_experiment(ROOT / "configs/gate1.v4.example.toml", ROOT)
    snapshot = MemorySnapshot(
        captured_at="now",
        monotonic_seconds=1,
        free_percent=50,
        page_size=16384,
        pages_free=1,
        pages_active=1,
        pages_inactive=1,
        pages_speculative=1,
        pages_wired=1,
        pages_compressor=1,
        pageins=1,
        pageouts=1,
        swap_total_bytes=1,
        swap_used_bytes=1,
        swap_free_bytes=1,
        pressure_level="normal",
    )
    monkeypatch.setattr(runner, "memory_snapshot", lambda: snapshot)
    monkeypatch.setattr(runner.time, "monotonic", lambda: 0.0)
    monkeypatch.setattr(runner.time, "sleep", lambda _seconds: None)
    assert len(runner._wait_for_memory_recovery(spec)) == 3


def test_native_critical_event_is_detected(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    path.write_text('{"kind":"pressure","level":"critical"}\n', encoding="utf-8")
    assert runner._native_critical_seen(path) is True
