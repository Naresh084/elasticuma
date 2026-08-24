from __future__ import annotations

import mmap
import os
import signal
import time
from dataclasses import dataclass
from pathlib import Path

from .macos import hardware_snapshot, memory_snapshot
from .util import atomic_write_json, utc_now

MAX_PRESSURE_MIB = 4096
MAX_MEMORY_FRACTION = 0.15
START_MIN_FREE_PERCENT = 25.0
STOP_MIN_FREE_PERCENT = 14.0


@dataclass(frozen=True)
class PressurePlan:
    requested_mib: int
    maximum_mib: int
    free_percent: float | None
    allowed: bool
    reasons: tuple[str, ...]


def validate_pressure_request(requested_mib: int) -> PressurePlan:
    hardware = hardware_snapshot()
    memory = memory_snapshot()
    fraction_cap = int(hardware.memory_bytes * MAX_MEMORY_FRACTION / (1024**2))
    maximum = min(MAX_PRESSURE_MIB, fraction_cap)
    reasons: list[str] = []
    if requested_mib <= 0:
        reasons.append("requested pressure must be positive")
    if requested_mib > maximum:
        reasons.append(f"requested {requested_mib} MiB exceeds safe cap {maximum} MiB")
    if memory.free_percent is None:
        reasons.append("memory_pressure did not report free percentage")
    elif memory.free_percent < START_MIN_FREE_PERCENT:
        reasons.append(
            f"current free percentage {memory.free_percent:.1f}% is below the "
            f"{START_MIN_FREE_PERCENT:.1f}% start guard"
        )
    return PressurePlan(
        requested_mib=requested_mib,
        maximum_mib=maximum,
        free_percent=memory.free_percent,
        allowed=not reasons,
        reasons=tuple(reasons),
    )


def run_pressure_worker(
    requested_mib: int,
    *,
    ready_path: Path,
    receipt_path: Path,
    check_interval_seconds: float = 0.5,
) -> int:
    plan = validate_pressure_request(requested_mib)
    if not plan.allowed:
        atomic_write_json(
            receipt_path,
            {
                "schema_version": 1,
                "state": "refused",
                "captured_at": utc_now(),
                "plan": plan,
            },
        )
        return 2

    stop = False

    def request_stop(_signum: int, _frame: object) -> None:
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    size = requested_mib * 1024**2
    region = mmap.mmap(-1, size, access=mmap.ACCESS_WRITE)
    page_size = 16 * 1024
    allocated = 0
    stop_reason = "signal"
    try:
        chunk = 64 * 1024**2
        while allocated < size and not stop:
            end = min(size, allocated + chunk)
            for offset in range(allocated, end, page_size):
                region[offset : offset + 1] = b"\x01"
            allocated = end
            current = memory_snapshot()
            if current.free_percent is not None and current.free_percent < STOP_MIN_FREE_PERCENT:
                stop_reason = "free-percentage-guard"
                stop = True
        if stop:
            atomic_write_json(
                receipt_path,
                {
                    "schema_version": 1,
                    "state": "stopped-before-ready",
                    "captured_at": utc_now(),
                    "allocated_bytes": allocated,
                    "reason": stop_reason,
                },
            )
            return 3
        ready_path.parent.mkdir(parents=True, exist_ok=True)
        ready_path.write_text(f"{os.getpid()}\n", encoding="utf-8")
        while not stop:
            time.sleep(check_interval_seconds)
            current = memory_snapshot()
            if current.free_percent is not None and current.free_percent < STOP_MIN_FREE_PERCENT:
                stop_reason = "free-percentage-guard"
                break
        atomic_write_json(
            receipt_path,
            {
                "schema_version": 1,
                "state": "complete",
                "captured_at": utc_now(),
                "allocated_bytes": allocated,
                "reason": stop_reason,
            },
        )
        return 0
    finally:
        ready_path.unlink(missing_ok=True)
        region.close()
