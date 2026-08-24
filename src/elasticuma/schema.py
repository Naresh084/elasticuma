from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

SCHEMA_VERSION = 1
EvidenceState = Literal["raw", "admitted", "diagnostic", "projected", "rejected"]


@dataclass(frozen=True)
class HardwareSnapshot:
    captured_at: str
    model_identifier: str | None
    chip: str
    cpu_cores: int
    gpu_cores: int | None
    memory_bytes: int
    macos_version: str
    machine_arch: str


@dataclass(frozen=True)
class MemorySnapshot:
    captured_at: str
    monotonic_seconds: float
    free_percent: float | None
    page_size: int
    pages_free: int | None
    pages_active: int | None
    pages_inactive: int | None
    pages_speculative: int | None
    pages_wired: int | None
    pages_compressor: int | None
    pageins: int | None
    pageouts: int | None
    swap_total_bytes: int | None
    swap_used_bytes: int | None
    swap_free_bytes: int | None
    pressure_level: Literal["normal", "warning", "critical", "unknown"]


@dataclass(frozen=True)
class ProcessSnapshot:
    captured_at: str
    monotonic_seconds: float
    root_pid: int
    process_count: int
    rss_bytes: int
    phys_footprint_bytes: int | None = None


@dataclass(frozen=True)
class PowerSnapshot:
    captured_at: str
    power_source: str
    battery_percent: int | None
    charging: bool | None
    low_power_mode: bool | None
    thermal_warning: bool | None
    performance_warning: bool | None


@dataclass(frozen=True)
class ModelPlan:
    repo_id: str
    requested_revision: str
    resolved_revision: str
    published_bytes: int
    cache_root: Path
    existing_snapshot: Path | None
    existing_cache_root: Path | None
    disk_free_bytes: int
    disk_reserve_bytes: int
    store_physical_bytes: int
    store_limit_bytes: int
    action: Literal["reuse", "download", "refuse"]
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class ArmSpec:
    name: str
    cache_mib: int
    command: tuple[str, ...]
    environment: dict[str, str] = field(default_factory=dict)
    pressure_mib: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExperimentSpec:
    name: str
    model_repo: str
    model_revision: str
    prompt_file: Path
    context_tokens: int
    max_tokens: int
    seed: int
    warmups: int
    repetitions: int
    sample_interval_seconds: float
    start_min_free_percent: float
    recovery_stable_samples: int
    recovery_timeout_seconds: float
    min_free_percent: float
    max_swap_delta_bytes: int
    warmup_max_swap_delta_bytes: int
    timeout_seconds: float
    adapter: str
    worker_process_name: str | None
    required_power_source: str | None
    require_low_power_mode_off: bool
    require_no_thermal_warning: bool
    require_native_pressure_monitor: bool
    require_output_parity: bool
    require_token_id_parity: bool
    require_expert_telemetry: bool
    fail_fast: bool
    allow_live_pressure: bool
    arms: tuple[ArmSpec, ...]


@dataclass
class RuntimeResult:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    prompt_tps: float | None = None
    decode_tps: float | None = None
    ttft_seconds: float | None = None
    output_sha256: str | None = None
    token_ids_sha256: str | None = None
    expert_hit_rate: float | None = None
    expert_miss_count: int | None = None
    expert_access_count: int | None = None
    expert_cache_slots: int | None = None
    expert_miss_bytes: int | None = None
    expert_materialized_bytes: int | None = None
    expert_evictions: int | None = None
    mtp_drafted_tokens: int | None = None
    mtp_accepted_tokens: int | None = None
    expert_residency_hot_slots: int | None = None
    expert_volatile_transitions: int | None = None
    expert_residency_revalidations: int | None = None
    expert_retained_revalidations: int | None = None
    expert_empty_recoveries: int | None = None
    expert_explicit_discards: int | None = None
    expert_residency_invalidated_slots: int | None = None
    expert_reclaimed_bytes: int | None = None
    runtime_payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class RunRecord:
    schema_version: int
    run_id: str
    evidence_state: EvidenceState
    experiment_name: str
    arm_name: str
    schedule_index: int
    repetition: int
    warmup: bool
    started_at: str
    finished_at: str | None
    duration_seconds: float | None
    model_repo: str
    model_revision: str
    model_path: str
    prompt_sha256: str
    command_sha256: str
    cache_mib: int
    pressure_mib: int
    return_code: int | None
    timed_out: bool
    stdout_path: str
    stderr_path: str
    hardware: HardwareSnapshot
    memory_before: MemorySnapshot
    memory_after: MemorySnapshot | None
    memory_samples: list[MemorySnapshot]
    process_samples: list[ProcessSnapshot]
    power_before: PowerSnapshot
    power_after: PowerSnapshot | None
    native_pressure_monitor_sha256: str | None
    native_pressure_events: list[dict[str, Any]]
    runtime: RuntimeResult
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AdmissionDecision:
    run_id: str
    admitted: bool
    reasons: tuple[str, ...]
