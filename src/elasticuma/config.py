from __future__ import annotations

import tomllib
from math import isfinite
from pathlib import Path
from typing import Any

from .schema import ArmSpec, ExperimentSpec


class ConfigError(ValueError):
    pass


def _positive_int(payload: dict[str, Any], key: str, default: int | None = None) -> int:
    value = payload.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ConfigError(f"{key} must be a positive integer")
    return value


def _positive_float(payload: dict[str, Any], key: str, default: float) -> float:
    value = payload.get(key, default)
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not isfinite(value)
        or value <= 0
    ):
        raise ConfigError(f"{key} must be positive")
    return float(value)


def _resolve_path(project_root: Path, value: object, key: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{key} must be a path string")
    path = Path(value).expanduser()
    return path if path.is_absolute() else project_root / path


def _parse_arm(payload: object, index: int) -> ArmSpec:
    if not isinstance(payload, dict):
        raise ConfigError(f"arms[{index}] must be a table")
    name = payload.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ConfigError(f"arms[{index}].name is required")
    command = payload.get("command")
    if (
        not isinstance(command, list)
        or not command
        or not all(isinstance(item, str) and item for item in command)
    ):
        raise ConfigError(f"arms[{index}].command must be a non-empty string array")
    environment = payload.get("environment", {})
    if not isinstance(environment, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in environment.items()
    ):
        raise ConfigError(f"arms[{index}].environment must contain string pairs")
    metadata = payload.get("metadata", {})
    if not isinstance(metadata, dict):
        raise ConfigError(f"arms[{index}].metadata must be a table")
    cache_mib = _positive_int(payload, "cache_mib")
    pressure_mib = payload.get("pressure_mib", 0)
    if isinstance(pressure_mib, bool) or not isinstance(pressure_mib, int) or pressure_mib < 0:
        raise ConfigError(f"arms[{index}].pressure_mib must be a non-negative integer")
    return ArmSpec(
        name=name,
        cache_mib=cache_mib,
        command=tuple(command),
        environment=dict(environment),
        pressure_mib=pressure_mib,
        metadata=dict(metadata),
    )


def load_experiment(path: Path, project_root: Path) -> ExperimentSpec:
    with path.open("rb") as handle:
        payload = tomllib.load(handle)
    experiment = payload.get("experiment")
    if not isinstance(experiment, dict):
        raise ConfigError("[experiment] table is required")
    arms_raw = payload.get("arms")
    if not isinstance(arms_raw, list) or not arms_raw:
        raise ConfigError("at least one [[arms]] table is required")
    arms = tuple(_parse_arm(item, index) for index, item in enumerate(arms_raw))
    names = [arm.name for arm in arms]
    if len(set(names)) != len(names):
        raise ConfigError("arm names must be unique")
    model_repo = experiment.get("model_repo")
    model_revision = experiment.get("model_revision")
    name = experiment.get("name")
    if not all(
        isinstance(value, str) and value.strip() for value in (name, model_repo, model_revision)
    ):
        raise ConfigError("experiment name, model_repo, and model_revision are required")
    prompt_file = _resolve_path(project_root, experiment.get("prompt_file"), "prompt_file")
    if not prompt_file.is_file():
        raise ConfigError(f"prompt file does not exist: {prompt_file}")
    adapter = experiment.get("adapter", "command-json-v1")
    if adapter != "command-json-v1":
        raise ConfigError(f"unsupported adapter: {adapter}")
    worker_process_name = experiment.get("worker_process_name")
    if worker_process_name is not None and (
        not isinstance(worker_process_name, str)
        or not worker_process_name
        or len(worker_process_name) > 64
        or not all(character.isalnum() or character in "._-" for character in worker_process_name)
    ):
        raise ConfigError("worker_process_name must be a safe process basename")
    required_power_source = experiment.get("required_power_source")
    if required_power_source not in {None, "AC Power", "Battery Power", "UPS Power"}:
        raise ConfigError("required_power_source must be AC Power, Battery Power, or UPS Power")
    require_output_parity = experiment.get("require_output_parity", True)
    require_token_id_parity = experiment.get("require_token_id_parity", False)
    require_expert_telemetry = experiment.get("require_expert_telemetry", False)
    require_low_power_mode_off = experiment.get("require_low_power_mode_off", True)
    require_no_thermal_warning = experiment.get("require_no_thermal_warning", True)
    require_native_pressure_monitor = experiment.get("require_native_pressure_monitor", False)
    fail_fast = experiment.get("fail_fast", False)
    allow_live_pressure = experiment.get("allow_live_pressure", False)
    boolean_fields = {
        "require_output_parity": require_output_parity,
        "require_token_id_parity": require_token_id_parity,
        "require_expert_telemetry": require_expert_telemetry,
        "require_low_power_mode_off": require_low_power_mode_off,
        "require_no_thermal_warning": require_no_thermal_warning,
        "require_native_pressure_monitor": require_native_pressure_monitor,
        "fail_fast": fail_fast,
        "allow_live_pressure": allow_live_pressure,
    }
    invalid = [key for key, value in boolean_fields.items() if not isinstance(value, bool)]
    if invalid:
        raise ConfigError(f"{', '.join(invalid)} must be boolean")
    max_swap_delta_mib = experiment.get("max_swap_delta_mib", 128)
    if (
        isinstance(max_swap_delta_mib, bool)
        or not isinstance(max_swap_delta_mib, int)
        or max_swap_delta_mib < 0
    ):
        raise ConfigError("max_swap_delta_mib must be a non-negative integer")
    warmup_max_swap_delta_mib = experiment.get("warmup_max_swap_delta_mib", max_swap_delta_mib)
    if (
        isinstance(warmup_max_swap_delta_mib, bool)
        or not isinstance(warmup_max_swap_delta_mib, int)
        or warmup_max_swap_delta_mib < max_swap_delta_mib
    ):
        raise ConfigError(
            "warmup_max_swap_delta_mib must be an integer at least max_swap_delta_mib"
        )
    min_free_percent = experiment.get("min_free_percent", 12.0)
    if (
        isinstance(min_free_percent, bool)
        or not isinstance(min_free_percent, (int, float))
        or not isfinite(min_free_percent)
        or not 0 < min_free_percent <= 100
    ):
        raise ConfigError("min_free_percent must be finite and in (0, 100]")
    start_min_free_percent = experiment.get("start_min_free_percent", min_free_percent)
    if (
        isinstance(start_min_free_percent, bool)
        or not isinstance(start_min_free_percent, (int, float))
        or not isfinite(start_min_free_percent)
        or not min_free_percent <= start_min_free_percent <= 100
    ):
        raise ConfigError(
            "start_min_free_percent must be finite and between min_free_percent and 100"
        )
    return ExperimentSpec(
        name=str(name),
        model_repo=str(model_repo),
        model_revision=str(model_revision),
        prompt_file=prompt_file,
        context_tokens=_positive_int(experiment, "context_tokens"),
        max_tokens=_positive_int(experiment, "max_tokens"),
        seed=_positive_int(experiment, "seed", 1),
        warmups=_positive_int(experiment, "warmups", 1),
        repetitions=_positive_int(experiment, "repetitions", 5),
        sample_interval_seconds=_positive_float(experiment, "sample_interval_seconds", 0.5),
        start_min_free_percent=float(start_min_free_percent),
        recovery_stable_samples=_positive_int(experiment, "recovery_stable_samples", 3),
        recovery_timeout_seconds=_positive_float(experiment, "recovery_timeout_seconds", 60.0),
        min_free_percent=float(min_free_percent),
        max_swap_delta_bytes=max_swap_delta_mib * 1024**2,
        warmup_max_swap_delta_bytes=warmup_max_swap_delta_mib * 1024**2,
        timeout_seconds=_positive_float(experiment, "timeout_seconds", 900.0),
        adapter=str(adapter),
        worker_process_name=worker_process_name,
        required_power_source=required_power_source,
        require_low_power_mode_off=require_low_power_mode_off,
        require_no_thermal_warning=require_no_thermal_warning,
        require_native_pressure_monitor=require_native_pressure_monitor,
        require_output_parity=require_output_parity,
        require_token_id_parity=require_token_id_parity,
        require_expert_telemetry=require_expert_telemetry,
        fail_fast=fail_fast,
        allow_live_pressure=allow_live_pressure,
        arms=arms,
    )


def balanced_schedule(spec: ExperimentSpec) -> list[tuple[ArmSpec, int, bool]]:
    schedule: list[tuple[ArmSpec, int, bool]] = []
    for warmup in range(spec.warmups):
        order = spec.arms if warmup % 2 == 0 else tuple(reversed(spec.arms))
        schedule.extend((arm, warmup, True) for arm in order)
    for repetition in range(spec.repetitions):
        order = spec.arms if repetition % 2 == 0 else tuple(reversed(spec.arms))
        schedule.extend((arm, repetition, False) for arm in order)
    return schedule
