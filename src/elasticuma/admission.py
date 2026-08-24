from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from .schema import AdmissionDecision, ExperimentSpec, RunRecord
from .util import atomic_write_json, jsonable, utc_now


def _swap_used(snapshot: object) -> int | None:
    if isinstance(snapshot, dict):
        value = snapshot.get("swap_used_bytes")
    else:
        value = getattr(snapshot, "swap_used_bytes", None)
    return int(value) if isinstance(value, int) and not isinstance(value, bool) else None


def _free_percent(snapshot: object) -> float | None:
    if isinstance(snapshot, dict):
        value = snapshot.get("free_percent")
    else:
        value = getattr(snapshot, "free_percent", None)
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _runtime(record: RunRecord | dict[str, Any]) -> object:
    return record["runtime"] if isinstance(record, dict) else record.runtime


def _field(value: object, name: str) -> object:
    return value.get(name) if isinstance(value, dict) else getattr(value, name, None)


def decide_run(record: RunRecord | dict[str, Any], spec: ExperimentSpec) -> AdmissionDecision:
    get = record.get if isinstance(record, dict) else lambda key: getattr(record, key)
    reasons: list[str] = []
    if bool(get("warmup")):
        reasons.append("warmup rows cannot be admitted")
    if get("return_code") != 0:
        reasons.append(f"runtime return code is {get('return_code')}")
    if bool(get("timed_out")):
        reasons.append("runtime timed out")
    errors = get("errors") or []
    reasons.extend(str(error) for error in errors)
    runtime = _runtime(record)
    completion = _field(runtime, "completion_tokens")
    decode_tps = _field(runtime, "decode_tps")
    output_hash = _field(runtime, "output_sha256")
    token_hash = _field(runtime, "token_ids_sha256")
    expert_hit_rate = _field(runtime, "expert_hit_rate")
    expert_misses = _field(runtime, "expert_miss_count")
    expert_accesses = _field(runtime, "expert_access_count")
    if not isinstance(completion, int) or isinstance(completion, bool) or completion <= 0:
        reasons.append("completion token count is missing or non-positive")
    if not isinstance(decode_tps, (int, float)) or isinstance(decode_tps, bool) or decode_tps <= 0:
        reasons.append("decode throughput is missing or non-positive")
    if not isinstance(output_hash, str) or len(output_hash) != 64:
        reasons.append("output SHA-256 is missing")
    if spec.require_token_id_parity and (not isinstance(token_hash, str) or len(token_hash) != 64):
        reasons.append("token-id SHA-256 is missing")
    if spec.require_expert_telemetry:
        if (
            not isinstance(expert_hit_rate, (int, float))
            or isinstance(expert_hit_rate, bool)
            or not 0 <= expert_hit_rate <= 1
        ):
            reasons.append("expert hit rate is missing or outside [0, 1]")
        if (
            not isinstance(expert_misses, int)
            or isinstance(expert_misses, bool)
            or expert_misses < 0
        ):
            reasons.append("expert miss count is missing or negative")
        if (
            not isinstance(expert_accesses, int)
            or isinstance(expert_accesses, bool)
            or expert_accesses <= 0
        ):
            reasons.append("expert access count is missing or non-positive")
    power_before = get("power_before")
    power_after = get("power_after")
    if spec.required_power_source:
        observed_sources = {
            _field(snapshot, "power_source") for snapshot in (power_before, power_after)
        }
        if observed_sources != {spec.required_power_source}:
            reasons.append("required power source was not stable for the complete run")
    if spec.require_low_power_mode_off and any(
        _field(snapshot, "low_power_mode") is not False for snapshot in (power_before, power_after)
    ):
        reasons.append("low-power mode was on or unobservable")
    if spec.require_no_thermal_warning and any(
        _field(snapshot, field) is not False
        for snapshot in (power_before, power_after)
        for field in ("thermal_warning", "performance_warning")
    ):
        reasons.append("thermal/performance warning was present or unobservable")
    if spec.require_native_pressure_monitor:
        monitor_hash = get("native_pressure_monitor_sha256")
        native_events = get("native_pressure_events")
        if not isinstance(monitor_hash, str) or len(monitor_hash) != 64:
            reasons.append("native pressure monitor hash is missing")
        if (
            not isinstance(native_events, list)
            or not native_events
            or _field(native_events[0], "kind") != "start"
        ):
            reasons.append("native pressure monitor start receipt is missing")
        elif any(_field(event, "level") == "critical" for event in native_events):
            reasons.append("native pressure monitor reported a critical event")
    samples = list(get("memory_samples") or [])
    before = get("memory_before")
    after = get("memory_after")
    free_values = [
        value
        for value in [_free_percent(before), *map(_free_percent, samples), _free_percent(after)]
        if value is not None
    ]
    if len(free_values) < 2:
        reasons.append("fewer than two valid memory-pressure observations")
    elif min(free_values) < spec.min_free_percent:
        reasons.append(
            f"minimum free percentage {min(free_values):.1f}% crossed "
            f"{spec.min_free_percent:.1f}% guard"
        )
    swap_before = _swap_used(before)
    swap_after = _swap_used(after)
    if swap_before is None or swap_after is None:
        reasons.append("swap telemetry is incomplete")
    elif max(0, swap_after - swap_before) > spec.max_swap_delta_bytes:
        reasons.append("swap growth exceeded experiment limit")
    return AdmissionDecision(
        run_id=str(get("run_id")),
        admitted=not reasons,
        reasons=tuple(reasons),
    )


def admit_experiment(
    project_root: Path,
    records: list[RunRecord],
    spec: ExperimentSpec,
) -> Path:
    decisions = [decide_run(record, spec) for record in records]
    measured = [record for record in records if not record.warmup]
    if spec.require_output_parity or spec.require_token_id_parity:
        output_hashes = {
            record.runtime.output_sha256
            for record in measured
            if record.runtime.output_sha256 is not None
        }
        token_hashes = {
            record.runtime.token_ids_sha256
            for record in measured
            if record.runtime.token_ids_sha256 is not None
        }
        output_failed = spec.require_output_parity and len(output_hashes) > 1
        token_failed = spec.require_token_id_parity and len(token_hashes) > 1
        if output_failed or token_failed:
            decisions = [
                AdmissionDecision(
                    run_id=decision.run_id,
                    admitted=False,
                    reasons=(*decision.reasons, "cross-arm deterministic output parity failed"),
                )
                for decision in decisions
            ]
    by_id = {decision.run_id: decision for decision in decisions}
    admitted = [
        jsonable(record)
        for record in records
        if by_id[record.run_id].admitted and not record.warmup
    ]
    payload = {
        "schema_version": 1,
        "created_at": utc_now(),
        "experiment": asdict(spec),
        "decisions": [asdict(decision) for decision in decisions],
        "admitted_count": len(admitted),
        "measured_count": len(measured),
        "complete": len(admitted) == len(measured),
        "records": admitted,
    }
    path = project_root / "artifacts/admitted" / f"{spec.name}.json"
    atomic_write_json(path, payload)
    return path
