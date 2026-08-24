from __future__ import annotations

from elasticuma import pressure
from elasticuma.schema import HardwareSnapshot, MemorySnapshot


def test_pressure_plan_enforces_fraction_cap(monkeypatch) -> None:
    monkeypatch.setattr(
        pressure,
        "hardware_snapshot",
        lambda: HardwareSnapshot(
            captured_at="now",
            model_identifier="Mac",
            chip="M1 Max",
            cpu_cores=10,
            gpu_cores=24,
            memory_bytes=32 * 1024**3,
            macos_version="26.5",
            machine_arch="arm64",
        ),
    )
    monkeypatch.setattr(
        pressure,
        "memory_snapshot",
        lambda: MemorySnapshot(
            captured_at="now",
            monotonic_seconds=0,
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
            swap_total_bytes=0,
            swap_used_bytes=0,
            swap_free_bytes=0,
            pressure_level="normal",
        ),
    )
    assert pressure.validate_pressure_request(2048).allowed is True
    assert pressure.validate_pressure_request(5000).allowed is False
