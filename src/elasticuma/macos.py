from __future__ import annotations

import ctypes
import json
import platform
import re
import subprocess
import time
from pathlib import Path

from .schema import HardwareSnapshot, MemorySnapshot, PowerSnapshot, ProcessSnapshot
from .util import utc_now


def pids_named(process_name: str) -> tuple[int, ...]:
    """Return PIDs for an exact process basename without reading command lines."""

    if (
        not process_name
        or len(process_name) > 64
        or not all(character.isalnum() or character in "._-" for character in process_name)
    ):
        raise ValueError("unsafe process basename")
    completed = subprocess.run(
        ["/usr/bin/pgrep", "-x", process_name],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode == 1:
        return ()
    if completed.returncode != 0:
        raise RuntimeError(f"pgrep failed for {process_name!r}: {completed.stderr.strip()}")
    try:
        return tuple(sorted(int(line) for line in completed.stdout.splitlines() if line.strip()))
    except ValueError as exc:
        raise RuntimeError("pgrep returned a non-integer PID") from exc


_SIZE_FACTORS = {
    "K": 1024,
    "M": 1024**2,
    "G": 1024**3,
    "T": 1024**4,
}


class TelemetryError(RuntimeError):
    pass


class _RUsageInfoV0(ctypes.Structure):
    _fields_ = [
        ("ri_uuid", ctypes.c_uint8 * 16),
        ("ri_user_time", ctypes.c_uint64),
        ("ri_system_time", ctypes.c_uint64),
        ("ri_pkg_idle_wkups", ctypes.c_uint64),
        ("ri_interrupt_wkups", ctypes.c_uint64),
        ("ri_pageins", ctypes.c_uint64),
        ("ri_wired_size", ctypes.c_uint64),
        ("ri_resident_size", ctypes.c_uint64),
        ("ri_phys_footprint", ctypes.c_uint64),
        ("ri_proc_start_abstime", ctypes.c_uint64),
        ("ri_proc_exit_abstime", ctypes.c_uint64),
    ]


def _process_phys_footprint(pid: int) -> int | None:
    """Read Apple's task-accounted physical footprint without shell parsing."""

    if platform.system() != "Darwin":
        return None
    libproc = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
    proc_pid_rusage = libproc.proc_pid_rusage
    proc_pid_rusage.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_void_p]
    proc_pid_rusage.restype = ctypes.c_int
    usage = _RUsageInfoV0()
    # RUSAGE_INFO_V0 is stable since macOS 10.9 and contains ri_phys_footprint.
    if proc_pid_rusage(pid, 0, ctypes.byref(usage)) != 0:
        return None
    return int(usage.ri_phys_footprint)


def _run(command: list[str], *, timeout: float = 15.0) -> str:
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return completed.stdout


def parse_size(value: str) -> int:
    match = re.fullmatch(r"\s*([0-9]+(?:\.[0-9]+)?)\s*([KMGT]?)B?\s*", value, re.I)
    if not match:
        raise ValueError(f"unrecognized size: {value!r}")
    number = float(match.group(1))
    unit = match.group(2).upper()
    return int(number * (_SIZE_FACTORS.get(unit, 1)))


def parse_vm_stat(text: str) -> tuple[int, dict[str, int]]:
    first, *lines = text.splitlines()
    page_match = re.search(r"page size of\s+(\d+) bytes", first)
    if not page_match:
        raise TelemetryError("vm_stat did not report a page size")
    page_size = int(page_match.group(1))
    values: dict[str, int] = {}
    for line in lines:
        match = re.match(r"([^:]+):\s+([0-9]+)\.?$", line.strip())
        if match:
            key = re.sub(r"\s+", "_", match.group(1).strip().lower())
            values[key] = int(match.group(2))
    return page_size, values


def parse_memory_pressure(text: str) -> float | None:
    match = re.search(r"System-wide memory free percentage:\s*([0-9.]+)%", text)
    return float(match.group(1)) if match else None


def parse_swapusage(text: str) -> tuple[int | None, int | None, int | None]:
    fields: dict[str, int] = {}
    for key in ("total", "used", "free"):
        match = re.search(rf"\b{key}\s*=\s*([0-9.]+[KMGT]?)", text, re.I)
        if match:
            fields[key] = parse_size(match.group(1))
    return fields.get("total"), fields.get("used"), fields.get("free")


def parse_power_source(text: str) -> tuple[str, int | None, bool | None]:
    source_match = re.search(r"Now drawing from '([^']+)'", text)
    source = source_match.group(1) if source_match else "unknown"
    percent_match = re.search(r"\b(\d{1,3})%;", text)
    percent = int(percent_match.group(1)) if percent_match else None
    lowered = text.lower()
    if "discharging" in lowered or "not charging" in lowered:
        charging = False
    elif "charging" in lowered or "charged" in lowered:
        charging = True
    else:
        charging = None
    return source, percent, charging


def parse_low_power_mode(text: str) -> bool | None:
    match = re.search(r"^\s*lowpowermode\s+([01])\s*$", text, re.MULTILINE)
    return bool(int(match.group(1))) if match else None


def parse_warning_absence(text: str, warning: str) -> bool | None:
    lowered = text.lower()
    if f"no {warning} warning level has been recorded" in lowered:
        return False
    if f"{warning} warning level" in lowered:
        return True
    return None


def _pressure_level(free_percent: float | None) -> str:
    if free_percent is None:
        return "unknown"
    if free_percent < 12:
        return "critical"
    if free_percent < 22:
        return "warning"
    return "normal"


def memory_snapshot() -> MemorySnapshot:
    if platform.system() != "Darwin":
        raise TelemetryError("macOS telemetry is available only on Darwin")
    vm_text = _run(["/usr/bin/vm_stat"])
    pressure_text = _run(["/usr/bin/memory_pressure"])
    swap_text = _run(["/usr/sbin/sysctl", "-n", "vm.swapusage"])
    page_size, values = parse_vm_stat(vm_text)
    free_percent = parse_memory_pressure(pressure_text)
    swap_total, swap_used, swap_free = parse_swapusage(swap_text)
    return MemorySnapshot(
        captured_at=utc_now(),
        monotonic_seconds=time.monotonic(),
        free_percent=free_percent,
        page_size=page_size,
        pages_free=values.get("pages_free"),
        pages_active=values.get("pages_active"),
        pages_inactive=values.get("pages_inactive"),
        pages_speculative=values.get("pages_speculative"),
        pages_wired=values.get("pages_wired_down"),
        pages_compressor=values.get("pages_occupied_by_compressor"),
        pageins=values.get("pageins"),
        pageouts=values.get("pageouts"),
        swap_total_bytes=swap_total,
        swap_used_bytes=swap_used,
        swap_free_bytes=swap_free,
        pressure_level=_pressure_level(free_percent),
    )


def power_snapshot() -> PowerSnapshot:
    if platform.system() != "Darwin":
        raise TelemetryError("macOS power telemetry is available only on Darwin")
    source, percent, charging = parse_power_source(_run(["/usr/bin/pmset", "-g", "batt"]))
    current = _run(["/usr/bin/pmset", "-g"])
    therm = _run(["/usr/bin/pmset", "-g", "therm"])
    supported_sources = {"AC Power", "Battery Power", "UPS Power"}
    return PowerSnapshot(
        captured_at=utc_now(),
        power_source=source if source in supported_sources else "unknown",
        battery_percent=percent,
        charging=charging,
        low_power_mode=parse_low_power_mode(current),
        thermal_warning=parse_warning_absence(therm, "thermal"),
        performance_warning=parse_warning_absence(therm, "performance"),
    )


def _safe_hardware_entry() -> dict[str, object]:
    raw = _run(["/usr/sbin/system_profiler", "SPHardwareDataType", "-json"])
    payload = json.loads(raw)
    rows = payload.get("SPHardwareDataType")
    if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
        raise TelemetryError("system_profiler returned no hardware row")
    return rows[0]


def _gpu_cores() -> int | None:
    try:
        raw = _run(["/usr/sbin/system_profiler", "SPDisplaysDataType", "-json"])
        payload = json.loads(raw)
        for row in payload.get("SPDisplaysDataType", []):
            if not isinstance(row, dict):
                continue
            for key in ("sppci_cores", "spdisplays_gpu_cores"):
                value = row.get(key)
                if isinstance(value, str) and (match := re.search(r"\d+", value)):
                    return int(match.group())
                if isinstance(value, int):
                    return value
    except (OSError, ValueError, subprocess.SubprocessError, json.JSONDecodeError):
        return None
    return None


def hardware_snapshot() -> HardwareSnapshot:
    row = _safe_hardware_entry()
    memory_bytes = int(_run(["/usr/sbin/sysctl", "-n", "hw.memsize"]).strip())
    cpu_cores = int(_run(["/usr/sbin/sysctl", "-n", "hw.ncpu"]).strip())
    macos_version = _run(["/usr/bin/sw_vers", "-productVersion"]).strip()
    chip = str(row.get("chip_type") or row.get("chip") or "unknown")
    return HardwareSnapshot(
        captured_at=utc_now(),
        model_identifier=str(row.get("machine_model") or "") or None,
        chip=chip,
        cpu_cores=cpu_cores,
        gpu_cores=_gpu_cores(),
        memory_bytes=memory_bytes,
        macos_version=macos_version,
        machine_arch=platform.machine(),
    )


def process_tree_rss(root_pid: int) -> ProcessSnapshot:
    output = _run(["/bin/ps", "-axo", "pid=,ppid=,rss="])
    rows: dict[int, tuple[int, int]] = {}
    for line in output.splitlines():
        parts = line.split()
        if len(parts) != 3:
            continue
        pid, ppid, rss_kib = map(int, parts)
        rows[pid] = (ppid, rss_kib)
    descendants = {root_pid}
    changed = True
    while changed:
        changed = False
        for pid, (ppid, _) in rows.items():
            if ppid in descendants and pid not in descendants:
                descendants.add(pid)
                changed = True
    rss_kib = sum(rows.get(pid, (0, 0))[1] for pid in descendants)
    footprints = [
        value for pid in descendants if (value := _process_phys_footprint(pid)) is not None
    ]
    return ProcessSnapshot(
        captured_at=utc_now(),
        monotonic_seconds=time.monotonic(),
        root_pid=root_pid,
        process_count=len(descendants),
        rss_bytes=rss_kib * 1024,
        phys_footprint_bytes=sum(footprints) if footprints else None,
    )


def safe_public_hardware_dict() -> dict[str, object]:
    """Return hardware data with machine identifiers deliberately omitted."""
    snapshot = hardware_snapshot()
    return {
        "captured_at": snapshot.captured_at,
        "model_identifier": snapshot.model_identifier,
        "chip": snapshot.chip,
        "cpu_cores": snapshot.cpu_cores,
        "gpu_cores": snapshot.gpu_cores,
        "memory_bytes": snapshot.memory_bytes,
        "macos_version": snapshot.macos_version,
        "machine_arch": snapshot.machine_arch,
    }


def command_exists(path: str | Path) -> bool:
    return Path(path).is_file()
