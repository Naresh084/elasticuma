from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from elasticuma.admission import decide_run
from elasticuma.config import load_experiment

ROOT = Path(__file__).resolve().parents[1]
GATE1_FIXTURE = ROOT / "tests/fixtures/research/gate1.toml"


def _snapshot(*, free_percent: float = 40.0, swap_used_bytes: int = 0) -> dict[str, object]:
    return {"free_percent": free_percent, "swap_used_bytes": swap_used_bytes}


def _valid_record() -> dict[str, object]:
    return {
        "run_id": "test-run",
        "warmup": False,
        "return_code": 0,
        "timed_out": False,
        "errors": [],
        "runtime": {
            "completion_tokens": 32,
            "decode_tps": 12.5,
            "output_sha256": "a" * 64,
            "token_ids_sha256": None,
            "expert_hit_rate": 0.75,
            "expert_miss_count": 10,
            "expert_access_count": 40,
        },
        "memory_before": _snapshot(),
        "memory_samples": [_snapshot()],
        "memory_after": _snapshot(),
        "power_before": {
            "power_source": "AC Power",
            "low_power_mode": False,
            "thermal_warning": False,
            "performance_warning": False,
        },
        "power_after": {
            "power_source": "AC Power",
            "low_power_mode": False,
            "thermal_warning": False,
            "performance_warning": False,
        },
        "native_pressure_monitor_sha256": "b" * 64,
        "native_pressure_events": [
            {"schemaVersion": 1, "kind": "start", "monotonicNanoseconds": 10}
        ],
    }


def test_text_only_runtime_is_admitted_when_token_parity_is_capability_gated() -> None:
    spec = load_experiment(GATE1_FIXTURE, ROOT)
    decision = decide_run(_valid_record(), spec)
    assert decision.admitted is True


def test_token_hash_is_required_when_policy_enables_it() -> None:
    spec = load_experiment(GATE1_FIXTURE, ROOT)
    strict = replace(spec, require_token_id_parity=True)
    decision = decide_run(_valid_record(), strict)
    assert decision.admitted is False
    assert "token-id SHA-256 is missing" in decision.reasons
