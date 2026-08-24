from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
import uuid
from collections.abc import Iterable
from pathlib import Path
from typing import BinaryIO

from .adapters import CommandResultAdapter
from .config import balanced_schedule
from .locks import ProcessLock
from .macos import (
    hardware_snapshot,
    memory_snapshot,
    pids_named,
    power_snapshot,
    process_tree_rss,
)
from .model_store import resolve_registered
from .native_pressure import load_pressure_events, monitor_binary
from .schema import (
    SCHEMA_VERSION,
    ArmSpec,
    ExperimentSpec,
    MemorySnapshot,
    RunRecord,
    RuntimeResult,
)
from .util import atomic_write_json, sha256_file, sha256_text, utc_now


def _render(value: str, replacements: dict[str, str]) -> str:
    rendered = value
    for key, replacement in replacements.items():
        rendered = rendered.replace("{" + key + "}", replacement)
    unresolved = [part for part in replacements if "{" + part + "}" in rendered]
    if unresolved:
        raise ValueError(f"unresolved command placeholders: {unresolved}")
    return rendered


def _command(
    arm: ArmSpec,
    spec: ExperimentSpec,
    *,
    model_path: Path,
    result_path: Path,
) -> list[str]:
    replacements = {
        "model_path": str(model_path),
        "prompt_file": str(spec.prompt_file),
        "cache_mib": str(arm.cache_mib),
        "context_tokens": str(spec.context_tokens),
        "max_tokens": str(spec.max_tokens),
        "seed": str(spec.seed),
        "result_path": str(result_path),
    }
    return [_render(item, replacements) for item in arm.command]


def _terminate(process: subprocess.Popen[bytes], *, grace_seconds: float = 8.0) -> None:
    if process.poll() is not None:
        return
    # Every managed worker is launched with start_new_session=True. Signal that
    # process group so a wrapper cannot exit while leaving its native model child
    # resident and invalidating subsequent measurements.
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            return
        process.wait(timeout=grace_seconds)


def _start_pressure(
    project_root: Path,
    arm: ArmSpec,
    run_dir: Path,
    *,
    allowed: bool,
) -> subprocess.Popen[bytes] | None:
    if arm.pressure_mib == 0:
        return None
    if not allowed:
        raise RuntimeError(
            f"arm {arm.name!r} requests live pressure but experiment.allow_live_pressure is false"
        )
    ready = run_dir / "pressure.ready"
    receipt = run_dir / "pressure-receipt.json"
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "elasticuma.cli",
            "_pressure-worker",
            "--mib",
            str(arm.pressure_mib),
            "--ready",
            str(ready),
            "--receipt",
            str(receipt),
        ],
        cwd=project_root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if ready.is_file():
            return process
        if process.poll() is not None:
            raise RuntimeError(f"pressure worker exited before ready with {process.returncode}")
        time.sleep(0.1)
    _terminate(process)
    raise RuntimeError("pressure worker did not become ready within 30 seconds")


def _start_native_pressure_monitor(
    project_root: Path, run_dir: Path
) -> tuple[subprocess.Popen[bytes], BinaryIO, BinaryIO, Path, str]:
    binary = monitor_binary(project_root)
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise RuntimeError(f"native pressure monitor is missing; run `make native`: {binary}")
    events_path = run_dir / "native-pressure-events.jsonl"
    stderr_path = run_dir / "native-pressure-monitor.stderr.log"
    stdout = events_path.open("wb", buffering=0)
    stderr = stderr_path.open("wb", buffering=0)
    process: subprocess.Popen[bytes] | None = None
    try:
        process = subprocess.Popen(
            [str(binary)],
            cwd=project_root,
            stdout=stdout,
            stderr=stderr,
            start_new_session=True,
        )
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if events_path.is_file() and events_path.stat().st_size > 0:
                return process, stdout, stderr, events_path, sha256_file(binary)
            if process.poll() is not None:
                raise RuntimeError(
                    f"native pressure monitor exited before ready with {process.returncode}"
                )
            time.sleep(0.05)
        _terminate(process)
        raise RuntimeError("native pressure monitor did not become ready within 5 seconds")
    except BaseException:
        if process is not None:
            _terminate(process)
        stdout.close()
        stderr.close()
        raise


def _enforce_power_guard(spec: ExperimentSpec) -> None:
    current = power_snapshot()
    if spec.required_power_source and current.power_source != spec.required_power_source:
        raise RuntimeError(
            f"experiment requires {spec.required_power_source}, current source is "
            f"{current.power_source}"
        )
    if spec.require_low_power_mode_off and current.low_power_mode is not False:
        raise RuntimeError("experiment requires low-power mode to be observably off")
    if spec.require_no_thermal_warning and (
        current.thermal_warning is not False or current.performance_warning is not False
    ):
        raise RuntimeError("experiment requires no recorded thermal/performance warning")


def _wait_for_memory_recovery(spec: ExperimentSpec) -> list[MemorySnapshot]:
    snapshots: list[MemorySnapshot] = []
    stable = 0
    deadline = time.monotonic() + spec.recovery_timeout_seconds
    while time.monotonic() < deadline:
        current = memory_snapshot()
        snapshots.append(current)
        if (
            current.free_percent is not None
            and current.free_percent >= spec.start_min_free_percent
            and current.pressure_level == "normal"
        ):
            stable += 1
            if stable >= spec.recovery_stable_samples:
                return snapshots
        else:
            stable = 0
        time.sleep(1.0)
    last = snapshots[-1] if snapshots else None
    free = getattr(last, "free_percent", None)
    level = getattr(last, "pressure_level", "unknown")
    raise RuntimeError(
        f"memory did not recover to {spec.start_min_free_percent:.1f}% normal for "
        f"{spec.recovery_stable_samples} samples within {spec.recovery_timeout_seconds:.0f}s; "
        f"last free={free}, level={level}"
    )


def _native_critical_seen(path: Path | None) -> bool:
    if path is None:
        return False
    try:
        return b'"level":"critical"' in path.read_bytes()
    except FileNotFoundError:
        return False


def run_one(
    project_root: Path,
    spec: ExperimentSpec,
    arm: ArmSpec,
    *,
    model_path: Path,
    schedule_index: int,
    repetition: int,
    warmup: bool,
) -> RunRecord:
    run_id = f"{int(time.time() * 1000)}-{uuid.uuid4().hex[:12]}"
    run_dir = project_root / "artifacts/raw" / spec.name / run_id
    if run_dir.exists():
        raise RuntimeError(f"raw run directory already exists: {run_dir}")
    run_dir.mkdir(parents=True)
    stdout_path = run_dir / "stdout.log"
    stderr_path = run_dir / "stderr.log"
    result_path = run_dir / "runtime-result.json"
    command = _command(arm, spec, model_path=model_path, result_path=result_path)
    prompt = spec.prompt_file.read_text(encoding="utf-8")
    native_monitor: subprocess.Popen[bytes] | None = None
    native_stdout: BinaryIO | None = None
    native_stderr: BinaryIO | None = None
    native_events_path: Path | None = None
    native_monitor_sha256: str | None = None
    native_events: list[dict[str, object]] = []
    power_before = power_snapshot()
    before = memory_snapshot()
    started_at = utc_now()
    started_monotonic = time.monotonic()
    pressure_process: subprocess.Popen[bytes] | None = None
    runtime_process: subprocess.Popen[bytes] | None = None
    samples = []
    process_samples = []
    errors: list[str] = []
    timed_out = False
    return_code: int | None = None
    runtime_result = RuntimeResult()
    swap_growth_limit = spec.warmup_max_swap_delta_bytes if warmup else spec.max_swap_delta_bytes
    try:
        if spec.require_native_pressure_monitor:
            (
                native_monitor,
                native_stdout,
                native_stderr,
                native_events_path,
                native_monitor_sha256,
            ) = _start_native_pressure_monitor(project_root, run_dir)
        pressure_process = _start_pressure(
            project_root,
            arm,
            run_dir,
            allowed=spec.allow_live_pressure,
        )
        environment = os.environ.copy()
        environment.update(arm.environment)
        environment.update(
            {
                "ELASTICUMA_RUN_ID": run_id,
                "ELASTICUMA_RESULT_PATH": str(result_path),
                "ELASTICUMA_MODEL_PATH": str(model_path),
            }
        )
        with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
            runtime_process = subprocess.Popen(
                command,
                cwd=project_root,
                env=environment,
                stdout=stdout,
                stderr=stderr,
                start_new_session=True,
            )
            deadline = started_monotonic + spec.timeout_seconds
            while runtime_process.poll() is None:
                now = time.monotonic()
                if now >= deadline:
                    timed_out = True
                    errors.append("runtime timeout")
                    _terminate(runtime_process)
                    break
                try:
                    current = memory_snapshot()
                    samples.append(current)
                    process_samples.append(process_tree_rss(runtime_process.pid))
                    if (
                        current.free_percent is not None
                        and current.free_percent < spec.min_free_percent
                    ):
                        errors.append(
                            f"free percentage {current.free_percent:.1f}% crossed "
                            f"{spec.min_free_percent:.1f}% guard"
                        )
                        _terminate(runtime_process)
                        break
                    if (
                        before.swap_used_bytes is not None
                        and current.swap_used_bytes is not None
                        and max(0, current.swap_used_bytes - before.swap_used_bytes)
                        > swap_growth_limit
                    ):
                        errors.append("live swap growth crossed experiment limit")
                        _terminate(runtime_process)
                        break
                    if _native_critical_seen(native_events_path):
                        errors.append("native memory-pressure monitor reported critical")
                        _terminate(runtime_process)
                        break
                except (OSError, subprocess.SubprocessError, ValueError) as exc:
                    errors.append(f"telemetry error: {exc}")
                    _terminate(runtime_process)
                    break
                time.sleep(spec.sample_interval_seconds)
            return_code = runtime_process.wait(timeout=10)
        if return_code == 0 and not timed_out and not errors:
            try:
                runtime_result = CommandResultAdapter().parse(
                    stdout_path=stdout_path,
                    stderr_path=stderr_path,
                    result_path=result_path,
                )
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                errors.append(f"runtime result parse failed: {exc}")
    finally:
        if runtime_process is not None:
            _terminate(runtime_process)
        if pressure_process is not None:
            _terminate(pressure_process)
        if native_monitor is not None:
            _terminate(native_monitor)
        if native_stdout is not None:
            native_stdout.close()
        if native_stderr is not None:
            native_stderr.close()
    if native_events_path is not None:
        try:
            native_events = load_pressure_events(native_events_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"native pressure event parse failed: {exc}")
    after = memory_snapshot()
    power_after = power_snapshot()
    finished_monotonic = time.monotonic()
    record = RunRecord(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        evidence_state="raw",
        experiment_name=spec.name,
        arm_name=arm.name,
        schedule_index=schedule_index,
        repetition=repetition,
        warmup=warmup,
        started_at=started_at,
        finished_at=utc_now(),
        duration_seconds=finished_monotonic - started_monotonic,
        model_repo=spec.model_repo,
        model_revision=spec.model_revision,
        model_path=str(model_path),
        prompt_sha256=sha256_text(prompt),
        command_sha256=sha256_text(json.dumps(command, separators=(",", ":"))),
        cache_mib=arm.cache_mib,
        pressure_mib=arm.pressure_mib,
        return_code=return_code,
        timed_out=timed_out,
        stdout_path=str(stdout_path),
        stderr_path=str(stderr_path),
        hardware=hardware_snapshot(),
        memory_before=before,
        memory_after=after,
        memory_samples=samples,
        process_samples=process_samples,
        power_before=power_before,
        power_after=power_after,
        native_pressure_monitor_sha256=native_monitor_sha256,
        native_pressure_events=native_events,
        runtime=runtime_result,
        errors=errors,
    )
    atomic_write_json(run_dir / "record.json", record)
    return record


def run_experiment(project_root: Path, spec: ExperimentSpec) -> list[RunRecord]:
    _enforce_power_guard(spec)
    model_path = resolve_registered(project_root, spec.model_repo, spec.model_revision)
    schedule = balanced_schedule(spec)
    experiment_root = project_root / "artifacts/raw" / spec.name
    admitted_path = project_root / "artifacts/admitted" / f"{spec.name}.json"
    if admitted_path.exists() or any(experiment_root.glob("*/record.json")):
        raise RuntimeError(
            f"refusing to append or retry experiment {spec.name!r}; preserve raw data and "
            "use a newly named, documented protocol"
        )
    experiment_root.mkdir(parents=True, exist_ok=True)
    schedule_payload = [
        {
            "index": index,
            "arm": arm.name,
            "repetition": repetition,
            "warmup": warmup,
        }
        for index, (arm, repetition, warmup) in enumerate(schedule)
    ]
    atomic_write_json(experiment_root / "schedule.json", schedule_payload)
    records: list[RunRecord] = []
    with ProcessLock(project_root / ".locks/model-worker.lock"):
        for index, (arm, repetition, warmup) in enumerate(schedule):
            _enforce_power_guard(spec)
            recovery = _wait_for_memory_recovery(spec)
            atomic_write_json(
                experiment_root / f"recovery-{index:03d}.json",
                recovery,
            )
            if spec.worker_process_name:
                overlaps = pids_named(spec.worker_process_name)
                if overlaps:
                    raise RuntimeError(
                        f"refusing overlapping {spec.worker_process_name!r} workers: "
                        f"{len(overlaps)} process(es)"
                    )
            record = run_one(
                project_root,
                spec,
                arm,
                model_path=model_path,
                schedule_index=index,
                repetition=repetition,
                warmup=warmup,
            )
            records.append(record)
            if spec.worker_process_name and pids_named(spec.worker_process_name):
                raise RuntimeError(
                    f"{spec.worker_process_name!r} child remained after its wrapper exited"
                )
            _enforce_power_guard(spec)
            if spec.fail_fast and (record.return_code != 0 or record.timed_out or record.errors):
                raise RuntimeError(
                    f"fail-fast stopped after raw run {record.run_id}: "
                    f"return_code={record.return_code}, errors={record.errors}"
                )
    return records


def records_from_paths(paths: Iterable[Path]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in paths:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise ValueError(f"record is not a JSON object: {path}")
        rows.append(payload)
    return rows
