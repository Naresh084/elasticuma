from __future__ import annotations

import csv
import json
import random
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

from .util import atomic_write_json, utc_now


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def _nested(record: dict[str, Any], *keys: str) -> Any:
    value: Any = record
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _values(items: list[dict[str, Any]], *keys: str) -> list[float]:
    return [value for item in items if (value := _number(_nested(item, *keys))) is not None]


def _minimum_free(record: dict[str, Any]) -> float | None:
    snapshots = [record.get("memory_before"), *(record.get("memory_samples") or [])]
    if record.get("memory_after"):
        snapshots.append(record["memory_after"])
    values = [
        value
        for snapshot in snapshots
        if isinstance(snapshot, dict)
        if (value := _number(snapshot.get("free_percent"))) is not None
    ]
    return min(values) if values else None


def _peak_delta(
    record: dict[str, Any], field: str, *, multiplier_field: str | None = None
) -> float | None:
    before = record.get("memory_before")
    if not isinstance(before, dict):
        return None
    baseline = _number(before.get(field))
    if baseline is None:
        return None
    snapshots = [before, *(record.get("memory_samples") or [])]
    if isinstance(record.get("memory_after"), dict):
        snapshots.append(record["memory_after"])
    values = [
        value
        for snapshot in snapshots
        if isinstance(snapshot, dict)
        if (value := _number(snapshot.get(field))) is not None
    ]
    if not values:
        return None
    multiplier = 1.0
    if multiplier_field:
        multiplier = _number(before.get(multiplier_field)) or 1.0
    return max(0.0, max(values) - baseline) * multiplier


def _peak_process_rss(record: dict[str, Any]) -> float | None:
    values = [
        value
        for sample in record.get("process_samples") or []
        if isinstance(sample, dict)
        if (value := _number(sample.get("rss_bytes"))) is not None
    ]
    return max(values) if values else None


def _peak_process_phys_footprint(record: dict[str, Any]) -> float | None:
    values = [
        value
        for sample in record.get("process_samples") or []
        if isinstance(sample, dict)
        if (value := _number(sample.get("phys_footprint_bytes"))) is not None
    ]
    return max(values) if values else None


def _peak_pressure_score(record: dict[str, Any]) -> float | None:
    severity = {"normal": 0.0, "warning": 1.0, "critical": 2.0}
    snapshots = [record.get("memory_before"), *(record.get("memory_samples") or [])]
    if isinstance(record.get("memory_after"), dict):
        snapshots.append(record["memory_after"])
    scores = [
        severity[level]
        for snapshot in snapshots
        if isinstance(snapshot, dict)
        if isinstance((level := snapshot.get("pressure_level")), str)
        if level in severity
    ]
    return max(scores) if scores else None


def _native_pressure_event_score(record: dict[str, Any]) -> float:
    severity = {"normal": 0.0, "warning": 1.0, "critical": 2.0}
    scores = [
        severity[level]
        for event in record.get("native_pressure_events") or []
        if isinstance(event, dict)
        if isinstance((level := event.get("level")), str)
        if level in severity
    ]
    return max(scores, default=0.0)


def _delta(
    record: dict[str, Any], field: str, *, multiplier_field: str | None = None
) -> float | None:
    before = record.get("memory_before")
    after = record.get("memory_after")
    if not isinstance(before, dict) or not isinstance(after, dict):
        return None
    left = _number(before.get(field))
    right = _number(after.get(field))
    if left is None or right is None:
        return None
    multiplier = 1.0
    if multiplier_field:
        multiplier = (
            _number(after.get(multiplier_field)) or _number(before.get(multiplier_field)) or 1.0
        )
    return (right - left) * multiplier


def summarize(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, int, int], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        key = (
            str(record.get("arm_name")),
            int(record.get("cache_mib") or 0),
            int(record.get("pressure_mib") or 0),
        )
        groups[key].append(record)
    rows: list[dict[str, Any]] = []
    for (arm, cache_mib, pressure_mib), items in sorted(
        groups.items(), key=lambda pair: pair[0][1:]
    ):
        free_values = [value for item in items if (value := _minimum_free(item)) is not None]
        compressor = [
            value
            for item in items
            if (
                value := _delta(
                    item,
                    "pages_compressor",
                    multiplier_field="page_size",
                )
            )
            is not None
        ]
        swap = [value for item in items if (value := _delta(item, "swap_used_bytes")) is not None]
        peak_compressor = [
            value
            for item in items
            if (
                value := _peak_delta(
                    item,
                    "pages_compressor",
                    multiplier_field="page_size",
                )
            )
            is not None
        ]
        peak_swap = [
            value for item in items if (value := _peak_delta(item, "swap_used_bytes")) is not None
        ]
        peak_rss = [value for item in items if (value := _peak_process_rss(item)) is not None]
        peak_footprint = [
            value for item in items if (value := _peak_process_phys_footprint(item)) is not None
        ]
        peak_pressure = [
            value for item in items if (value := _peak_pressure_score(item)) is not None
        ]
        native_pressure = [_native_pressure_event_score(item) for item in items]
        rows.append(
            {
                "arm_name": arm,
                "cache_mib": cache_mib,
                "pressure_mib": pressure_mib,
                "samples": len(items),
                "median_decode_tps": _median(_values(items, "runtime", "decode_tps")),
                "median_prompt_tps": _median(_values(items, "runtime", "prompt_tps")),
                "median_ttft_seconds": _median(_values(items, "runtime", "ttft_seconds")),
                "median_expert_hit_rate": _median(_values(items, "runtime", "expert_hit_rate")),
                "median_expert_miss_count": _median(_values(items, "runtime", "expert_miss_count")),
                "median_expert_access_count": _median(
                    _values(items, "runtime", "expert_access_count")
                ),
                "median_expert_miss_bytes": _median(_values(items, "runtime", "expert_miss_bytes")),
                "median_materialized_bytes": _median(
                    _values(items, "runtime", "expert_materialized_bytes")
                ),
                "median_expert_reclaimed_bytes": _median(
                    _values(items, "runtime", "expert_reclaimed_bytes")
                ),
                "median_expert_empty_recoveries": _median(
                    _values(items, "runtime", "expert_empty_recoveries")
                ),
                "median_min_free_percent": _median(free_values),
                "median_peak_process_rss_bytes": _median(peak_rss),
                "median_peak_process_phys_footprint_bytes": _median(peak_footprint),
                "median_peak_pressure_score": _median(peak_pressure),
                "median_native_pressure_event_score": _median(native_pressure),
                "median_peak_compressor_growth_bytes": _median(peak_compressor),
                "median_peak_swap_growth_bytes": _median(peak_swap),
                "median_compressor_delta_bytes": _median(compressor),
                "median_swap_delta_bytes": _median(swap),
            }
        )
    return rows


def _paired_throughput_gaps(
    records: list[dict[str, Any]], small_arm: str, large_arm: str
) -> list[float]:
    by_arm: dict[str, dict[int, float]] = defaultdict(dict)
    for record in records:
        arm = str(record.get("arm_name"))
        repetition = record.get("repetition")
        throughput = _number(_nested(record, "runtime", "decode_tps"))
        if isinstance(repetition, int) and not isinstance(repetition, bool) and throughput:
            by_arm[arm][repetition] = throughput
    repetitions = sorted(set(by_arm[small_arm]) & set(by_arm[large_arm]))
    return [
        (by_arm[small_arm][repetition] - by_arm[large_arm][repetition])
        / by_arm[small_arm][repetition]
        for repetition in repetitions
    ]


def _bootstrap_median_ci(values: list[float], *, draws: int = 10_000) -> tuple[float, float] | None:
    if len(values) < 2:
        return None
    generator = random.Random(104729)
    medians = sorted(
        statistics.median(generator.choices(values, k=len(values))) for _ in range(draws)
    )
    lower = medians[int(0.025 * (draws - 1))]
    upper = medians[int(0.975 * (draws - 1))]
    return lower, upper


def purgeable_comparison(
    records: list[dict[str, Any]],
    *,
    candidate_arm: str,
    baseline_arms: list[str],
) -> dict[str, Any]:
    """Summarize a purgeable-cache candidate against paired fixed baselines."""

    summary = summarize(records)
    by_arm = {str(row["arm_name"]): row for row in summary}
    required = {candidate_arm, *baseline_arms}
    missing = sorted(required - set(by_arm))
    if missing:
        raise ValueError(f"purgeable comparison is missing arms: {', '.join(missing)}")
    candidate = by_arm[candidate_arm]
    comparisons: list[dict[str, Any]] = []
    for baseline_arm in baseline_arms:
        baseline = by_arm[baseline_arm]
        slowdowns = _paired_throughput_gaps(records, baseline_arm, candidate_arm)
        gains = [-value for value in slowdowns]
        baseline_tps = _number(baseline.get("median_decode_tps"))
        candidate_tps = _number(candidate.get("median_decode_tps"))
        baseline_footprint = _number(baseline.get("median_peak_process_phys_footprint_bytes"))
        candidate_footprint = _number(candidate.get("median_peak_process_phys_footprint_bytes"))
        baseline_pressure = (_number(baseline.get("median_peak_compressor_growth_bytes")) or 0) + (
            _number(baseline.get("median_peak_swap_growth_bytes")) or 0
        )
        candidate_pressure = (
            _number(candidate.get("median_peak_compressor_growth_bytes")) or 0
        ) + (_number(candidate.get("median_peak_swap_growth_bytes")) or 0)
        comparisons.append(
            {
                "baseline_arm": baseline_arm,
                "candidate_arm": candidate_arm,
                "paired_repetitions": len(gains),
                "paired_candidate_gains": gains,
                "paired_median_candidate_gain": statistics.median(gains) if gains else None,
                "paired_bootstrap_median_gain_ci95": _bootstrap_median_ci(gains),
                "aggregate_median_candidate_gain": (
                    candidate_tps / baseline_tps - 1
                    if candidate_tps is not None and baseline_tps
                    else None
                ),
                "hit_rate_point_gain": (
                    (_number(candidate.get("median_expert_hit_rate")) or 0)
                    - (_number(baseline.get("median_expert_hit_rate")) or 0)
                ),
                "peak_phys_footprint_reduction": (
                    (baseline_footprint - candidate_footprint) / baseline_footprint
                    if baseline_footprint and candidate_footprint is not None
                    else None
                ),
                "peak_compressor_plus_swap_benefit_bytes": (baseline_pressure - candidate_pressure),
            }
        )
    candidate_records = [
        record for record in records if str(record.get("arm_name")) == candidate_arm
    ]
    return {
        "candidate_arm": candidate_arm,
        "baseline_arms": baseline_arms,
        "summary": summary,
        "comparisons": comparisons,
        "candidate_empty_recoveries": _values(
            candidate_records, "runtime", "expert_empty_recoveries"
        ),
        "candidate_reclaimed_bytes": _values(
            candidate_records, "runtime", "expert_reclaimed_bytes"
        ),
    }


def gate1_verdict(
    summary: list[dict[str, Any]],
    records: list[dict[str, Any]] | None = None,
    *,
    gap_threshold: float = 0.15,
    minimum_repetitions: int = 5,
    minimum_directional_support: int = 4,
) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    comparisons: list[dict[str, Any]] = []
    by_pressure: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in summary:
        by_pressure[int(row["pressure_mib"])].append(row)
    for pressure_mib, rows in by_pressure.items():
        ordered = sorted(rows, key=lambda row: int(row["cache_mib"]))
        for small_index, small in enumerate(ordered):
            for large in ordered[small_index + 1 :]:
                small_tps = _number(small.get("median_decode_tps"))
                large_tps = _number(large.get("median_decode_tps"))
                small_hit = _number(small.get("median_expert_hit_rate"))
                large_hit = _number(large.get("median_expert_hit_rate"))
                if None in (small_tps, large_tps, small_hit, large_hit) or small_tps == 0:
                    continue
                throughput_gap = (small_tps - large_tps) / small_tps
                hit_improvement = large_hit - small_hit
                free_drop = (_number(small.get("median_min_free_percent")) or 0) - (
                    _number(large.get("median_min_free_percent")) or 0
                )
                large_compressor = _number(large.get("median_peak_compressor_growth_bytes"))
                small_compressor = _number(small.get("median_peak_compressor_growth_bytes"))
                if large_compressor is None:
                    large_compressor = _number(large.get("median_compressor_delta_bytes")) or 0
                if small_compressor is None:
                    small_compressor = _number(small.get("median_compressor_delta_bytes")) or 0
                compressor_growth = large_compressor - small_compressor
                large_swap = _number(large.get("median_peak_swap_growth_bytes"))
                small_swap = _number(small.get("median_peak_swap_growth_bytes"))
                if large_swap is None:
                    large_swap = _number(large.get("median_swap_delta_bytes")) or 0
                if small_swap is None:
                    small_swap = _number(small.get("median_swap_delta_bytes")) or 0
                swap_growth = large_swap - small_swap
                pressure_score_growth = (_number(large.get("median_peak_pressure_score")) or 0) - (
                    _number(small.get("median_peak_pressure_score")) or 0
                )
                native_pressure_score_growth = (
                    _number(large.get("median_native_pressure_event_score")) or 0
                ) - (_number(small.get("median_native_pressure_event_score")) or 0)
                pressure_evidence = (
                    free_drop >= 2
                    or compressor_growth >= 256 * 1024**2
                    or swap_growth > 0
                    or pressure_score_growth > 0
                    or native_pressure_score_growth > 0
                )
                paired_gaps = (
                    _paired_throughput_gaps(
                        records,
                        str(small["arm_name"]),
                        str(large["arm_name"]),
                    )
                    if records is not None
                    else []
                )
                paired_median = statistics.median(paired_gaps) if paired_gaps else None
                directional_support = sum(gap > 0 for gap in paired_gaps)
                if records is None:
                    repetition_evidence = True
                else:
                    repetition_evidence = (
                        len(paired_gaps) >= minimum_repetitions
                        and directional_support >= minimum_directional_support
                        and paired_median is not None
                        and paired_median >= gap_threshold
                    )
                passed = (
                    throughput_gap >= gap_threshold
                    and hit_improvement > 0
                    and pressure_evidence
                    and repetition_evidence
                )
                comparison = {
                    "pressure_mib": pressure_mib,
                    "smaller_arm": small["arm_name"],
                    "larger_arm": large["arm_name"],
                    "smaller_cache_mib": small["cache_mib"],
                    "larger_cache_mib": large["cache_mib"],
                    "throughput_gap": throughput_gap,
                    "hit_rate_improvement": hit_improvement,
                    "free_percent_drop": free_drop,
                    "compressor_growth_bytes": compressor_growth,
                    "swap_growth_bytes": swap_growth,
                    "pressure_score_growth": pressure_score_growth,
                    "native_pressure_score_growth": native_pressure_score_growth,
                    "pressure_evidence": pressure_evidence,
                    "paired_repetitions": len(paired_gaps),
                    "paired_throughput_gaps": paired_gaps,
                    "paired_median_gap": paired_median,
                    "paired_directional_support": directional_support,
                    "paired_bootstrap_median_ci95": _bootstrap_median_ci(paired_gaps),
                    "passes_gap_threshold": throughput_gap >= gap_threshold,
                    "passes_repetition_rule": repetition_evidence,
                    "passed": passed,
                }
                comparisons.append(comparison)
                if passed:
                    candidates.append(comparison)
    eligible_tradeoffs = [
        comparison
        for comparison in comparisons
        if comparison["hit_rate_improvement"] > 0 and comparison["pressure_evidence"]
    ]
    best_tradeoff = (
        max(eligible_tradeoffs, key=lambda item: float(item["throughput_gap"]))
        if eligible_tradeoffs
        else None
    )
    return {
        "passed": bool(candidates),
        "gap_threshold": gap_threshold,
        "minimum_repetitions": minimum_repetitions,
        "minimum_directional_support": minimum_directional_support,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "comparison_count": len(comparisons),
        "comparisons": comparisons,
        "best_observed_tradeoff": best_tradeoff,
        "interpretation": (
            "A recoverable pressure gap was detected. Controller work is authorized."
            if candidates
            else (
                "No admitted recoverable pressure gap was detected. "
                "Do not build the controller yet."
            )
        ),
    }


def analyze_admitted(admitted_path: Path, output_root: Path) -> tuple[Path, Path, Path]:
    with admitted_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict) or payload.get("complete") is not True:
        raise ValueError("analysis requires a complete admitted experiment")
    records = payload.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError("admitted experiment has no records")
    summary = summarize(records)
    verdict = gate1_verdict(summary, records)
    output_root.mkdir(parents=True, exist_ok=True)
    stem = admitted_path.stem
    json_path = output_root / f"{stem}-analysis.json"
    csv_path = output_root / f"{stem}-summary.csv"
    md_path = output_root / f"{stem}-gate1.md"
    atomic_write_json(
        json_path,
        {
            "schema_version": 1,
            "created_at": utc_now(),
            "source": str(admitted_path),
            "summary": summary,
            "gate1": verdict,
        },
    )
    fields = list(summary[0])
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(summary)
    lines = [
        "# Gate 1 analysis",
        "",
        f"Source: `{admitted_path}`",
        "",
        f"Verdict: **{'PASS' if verdict['passed'] else 'NOT PROVEN'}**",
        "",
        verdict["interpretation"],
        "",
        "## Fixed-policy summary",
        "",
        "| Arm | Cache MiB | Pressure MiB | n | Decode tok/s | Hit rate | "
        "Min free % | Peak compressor growth MiB |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary:
        compressor_mib = (_number(row.get("median_peak_compressor_growth_bytes")) or 0) / 1024**2
        lines.append(
            (
                "| {arm_name} | {cache_mib} | {pressure_mib} | {samples} | "
                "{tps} | {hit} | {free} | {compressor:.1f} |"
            ).format(
                arm_name=row["arm_name"],
                cache_mib=row["cache_mib"],
                pressure_mib=row["pressure_mib"],
                samples=row["samples"],
                tps=f"{row['median_decode_tps']:.3f}"
                if row["median_decode_tps"] is not None
                else "—",
                hit=f"{row['median_expert_hit_rate']:.4f}"
                if row["median_expert_hit_rate"] is not None
                else "—",
                free=f"{row['median_min_free_percent']:.1f}"
                if row["median_min_free_percent"] is not None
                else "—",
                compressor=compressor_mib,
            )
        )
    lines.extend(["", "## Candidate pressure gaps", ""])
    if verdict["candidates"]:
        for candidate in verdict["candidates"]:
            lines.append(f"- `{candidate}`")
    else:
        lines.append("- None admitted.")
    lines.extend(["", "## Strongest observed tradeoff", ""])
    if verdict["best_observed_tradeoff"]:
        best = verdict["best_observed_tradeoff"]
        interval = best["paired_bootstrap_median_ci95"]
        interval_text = (
            f"[{interval[0]:.2%}, {interval[1]:.2%}]" if interval is not None else "unavailable"
        )
        lines.extend(
            [
                f"- Pair: {best['smaller_arm']} → {best['larger_arm']}",
                f"- Aggregate median throughput gap: {best['throughput_gap']:.2%}",
                f"- Paired median gap: {best['paired_median_gap']:.2%}",
                "- Paired gaps: "
                + ", ".join(f"{value:.2%}" for value in best["paired_throughput_gaps"]),
                f"- Paired median bootstrap 95% interval: {interval_text}",
                f"- Directional support: {best['paired_directional_support']}/"
                f"{best['paired_repetitions']}",
                f"- Hit-rate improvement: {best['hit_rate_improvement']:.2%}",
                f"- Minimum-free drop: {best['free_percent_drop']:.1f} percentage points",
                f"- Passed 15% gap threshold: {best['passes_gap_threshold']}",
            ]
        )
    else:
        lines.append("- No pressure-backed hit-rate tradeoff was observed.")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, csv_path, md_path
