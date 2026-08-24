from __future__ import annotations

from pathlib import Path

from elasticuma.config import balanced_schedule, load_experiment

ROOT = Path(__file__).resolve().parents[1]


def test_example_config_is_valid_and_balanced() -> None:
    spec = load_experiment(ROOT / "configs/gate1.v4.example.toml", ROOT)
    schedule = balanced_schedule(spec)
    warmups = [row for row in schedule if row[2]]
    measured = [row for row in schedule if not row[2]]
    assert len(warmups) == 6
    assert len(measured) == 30
    assert spec.require_output_parity is True
    assert spec.require_token_id_parity is False
    assert spec.require_expert_telemetry is True
    assert spec.worker_process_name == "slipstream"
    assert spec.required_power_source == "AC Power"
    assert spec.require_low_power_mode_off is True
    assert spec.require_no_thermal_warning is True
    assert spec.require_native_pressure_monitor is True
    assert spec.fail_fast is True
    assert spec.start_min_free_percent == 40.0
    assert spec.recovery_stable_samples == 3
    assert spec.recovery_timeout_seconds == 60.0
    assert spec.max_swap_delta_bytes == 384 * 1024**2
    assert spec.warmup_max_swap_delta_bytes == 768 * 1024**2
    assert [row[0].name for row in measured[:12]] == [
        "cache-slots-16",
        "cache-slots-24",
        "cache-slots-32",
        "cache-slots-48",
        "cache-slots-64",
        "cache-slots-96",
        "cache-slots-96",
        "cache-slots-64",
        "cache-slots-48",
        "cache-slots-32",
        "cache-slots-24",
        "cache-slots-16",
    ]


def test_single_arm_dense_control_is_valid() -> None:
    spec = load_experiment(ROOT / "configs/qwen38.dense-control.example.toml", ROOT)
    schedule = balanced_schedule(spec)
    assert len(spec.arms) == 1
    assert len(schedule) == 6
    assert spec.require_expert_telemetry is False


def test_purgeable_reproduction_configs_are_valid() -> None:
    for name, live_pressure in (
        ("purgeable.pressure.example.toml", True),
        ("purgeable.nopressure.example.toml", False),
    ):
        spec = load_experiment(ROOT / "configs" / name, ROOT)
        assert len(spec.arms) == 3
        assert spec.allow_live_pressure is live_pressure
        assert len(balanced_schedule(spec)) == 18
