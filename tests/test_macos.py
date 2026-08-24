from __future__ import annotations

import subprocess

from elasticuma import macos
from elasticuma.macos import (
    parse_low_power_mode,
    parse_memory_pressure,
    parse_power_source,
    parse_size,
    parse_swapusage,
    parse_vm_stat,
    parse_warning_absence,
)


def test_parse_vm_stat() -> None:
    page_size, values = parse_vm_stat(
        """Mach Virtual Memory Statistics: (page size of 16384 bytes)
Pages free:                               3954.
Pages active:                           578126.
Pages wired down:                       184646.
Pages occupied by compressor:           703430.
Pageins:                               44389890.
Pageouts:                               522306.
"""
    )
    assert page_size == 16384
    assert values["pages_free"] == 3954
    assert values["pages_wired_down"] == 184646
    assert values["pages_occupied_by_compressor"] == 703430


def test_parse_memory_pressure() -> None:
    assert parse_memory_pressure("System-wide memory free percentage: 56%") == 56.0
    assert parse_memory_pressure("unavailable") is None


def test_parse_swapusage_and_sizes() -> None:
    total, used, free = parse_swapusage("total = 4096.00M  used = 1.50G  free = 2560.00M")
    assert total == 4096 * 1024**2
    assert used == int(1.5 * 1024**3)
    assert free == 2560 * 1024**2
    assert parse_size("20.5G") == int(20.5 * 1024**3)


def test_pids_named_uses_exact_basename_without_command_capture(monkeypatch) -> None:
    def fake_run(command, **kwargs):
        assert command == ["/usr/bin/pgrep", "-x", "slipstream"]
        assert kwargs["capture_output"] is True
        return subprocess.CompletedProcess(command, 0, stdout="42\n7\n", stderr="")

    monkeypatch.setattr(macos.subprocess, "run", fake_run)
    assert macos.pids_named("slipstream") == (7, 42)


def test_process_tree_snapshot_sums_rss_and_phys_footprint(monkeypatch) -> None:
    monkeypatch.setattr(
        macos,
        "_run",
        lambda command: "10 1 100\n11 10 200\n12 11 300\n99 1 900\n",
    )
    footprints = {10: 1_000, 11: 2_000, 12: 3_000}
    monkeypatch.setattr(macos, "_process_phys_footprint", footprints.get)

    snapshot = macos.process_tree_rss(10)

    assert snapshot.process_count == 3
    assert snapshot.rss_bytes == 600 * 1024
    assert snapshot.phys_footprint_bytes == 6_000


def test_power_parsers_exclude_battery_identifier() -> None:
    source, percent, charging = parse_power_source(
        "Now drawing from 'Battery Power'\n -InternalBattery-0\t37%; discharging; 0:38 remaining"
    )
    assert (source, percent, charging) == ("Battery Power", 37, False)
    assert parse_low_power_mode("Currently in use:\n lowpowermode  0\n") is False
    assert parse_warning_absence("No thermal warning level has been recorded", "thermal") is False
    assert parse_power_source("Now drawing from 'AC Power'\n18%; not charging") == (
        "AC Power",
        18,
        False,
    )
