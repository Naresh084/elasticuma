#!/usr/bin/env python3
# ruff: noqa: E501, RUF001
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from elasticuma.analysis import summarize
from elasticuma.util import atomic_write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--admitted", type=Path, required=True)
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def minimum_free(record: dict[str, Any]) -> float:
    snapshots = [record["memory_before"], *record["memory_samples"], record["memory_after"]]
    return min(float(snapshot["free_percent"]) for snapshot in snapshots)


def peak_growth(record: dict[str, Any], field: str, multiplier: int = 1) -> float:
    before = record["memory_before"]
    snapshots = [before, *record["memory_samples"], record["memory_after"]]
    baseline = int(before[field])
    peak = max(int(snapshot[field]) for snapshot in snapshots)
    return max(0, peak - baseline) * multiplier


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def source_spec() -> dict[str, Any]:
    return {
        "id": "gate1-v4",
        "label": "ElasticUMA Gate-1 v4 admitted evidence",
        "path": "evidence/measured.csv",
        "query": {
            "engine": "duckdb",
            "language": "sql",
            "description": "Load measured rows and attach the paired 16-to-96-slot gap.",
            "sql": (
                "WITH measured AS (\n"
                "  SELECT * FROM read_csv_auto('evidence/measured.csv')\n"
                "), pairs AS (\n"
                "  SELECT repetition,\n"
                "    (max(decode_tps) FILTER (expert_slots = 16) -\n"
                "     max(decode_tps) FILTER (expert_slots = 96)) /\n"
                "    max(decode_tps) FILTER (expert_slots = 16) AS paired_gap\n"
                "  FROM measured GROUP BY repetition\n"
                ")\n"
                "SELECT measured.*, pairs.paired_gap\n"
                "FROM measured LEFT JOIN pairs USING (repetition)"
            ),
            "executed_at": "2026-08-24T09:02:56Z",
            "tables_used": ["artifacts/admitted/gate1-m1max-qwen36-q4-v4.json"],
            "filters": [
                "Only automatically admitted non-warmup rows",
                "AC power, batch size one, 4,096 context, 256-token limit",
            ],
            "metric_definitions": [
                "Decode throughput = completion tokens / runtime decode seconds.",
                "Hit rate = (expert accesses - misses) / expert accesses.",
                "Paired gap = (16-slot tps - 96-slot tps) / 16-slot tps.",
            ],
        },
    }


def main() -> int:
    args = parse_args()
    admitted = json.loads(args.admitted.read_text(encoding="utf-8"))
    analysis = json.loads(args.analysis.read_text(encoding="utf-8"))
    if admitted.get("complete") is not True or admitted.get("admitted_count") != 30:
        raise SystemExit("report requires the complete 30-row Gate-1 v4 artifact")
    records = admitted["records"]
    output_dir = args.output_dir
    evidence_dir = output_dir / "evidence"

    measured_rows: list[dict[str, Any]] = []
    for record in sorted(records, key=lambda row: int(row["schedule_index"])):
        page_size = int(record["memory_before"]["page_size"])
        measured_rows.append(
            {
                "repetition": int(record["repetition"]),
                "schedule_index": int(record["schedule_index"]),
                "arm": str(record["arm_name"]),
                "expert_slots": int(record["runtime"]["expert_cache_slots"]),
                "cache_mib": int(record["cache_mib"]),
                "decode_tps": float(record["runtime"]["decode_tps"]),
                "prompt_tps": float(record["runtime"]["prompt_tps"]),
                "expert_hit_rate": float(record["runtime"]["expert_hit_rate"]),
                "expert_misses": int(record["runtime"]["expert_miss_count"]),
                "expert_accesses": int(record["runtime"]["expert_access_count"]),
                "minimum_free_percent": minimum_free(record),
                "peak_compressor_growth_gib": peak_growth(record, "pages_compressor", page_size)
                / 1024**3,
                "peak_swap_growth_mib": peak_growth(record, "swap_used_bytes") / 1024**2,
                "power_source": str(record["power_before"]["power_source"]),
                "native_warning_or_critical": any(
                    event.get("level") in {"warning", "critical"}
                    for event in record["native_pressure_events"]
                ),
            }
        )
    write_csv(evidence_dir / "measured.csv", measured_rows)

    summary = summarize(records)
    summary_rows: list[dict[str, Any]] = []
    for row in summary:
        slots = int(row["cache_mib"]) // 71
        summary_rows.append(
            {
                "expert_slots": slots,
                "cache_mib": int(row["cache_mib"]),
                "samples": int(row["samples"]),
                "median_decode_tps": float(row["median_decode_tps"]),
                "median_prompt_tps": float(row["median_prompt_tps"]),
                "hit_rate": float(row["median_expert_hit_rate"]),
                "minimum_free_rate": float(row["median_min_free_percent"]) / 100,
                "median_peak_compressor_growth_gib": float(
                    row["median_peak_compressor_growth_bytes"]
                )
                / 1024**3,
                "median_peak_swap_growth_mib": float(row["median_peak_swap_growth_bytes"])
                / 1024**2,
                "gate_threshold_tps": float(summary[0]["median_decode_tps"]) * 0.85,
                "safety_stop_rate": 0.25,
            }
        )
    write_csv(evidence_dir / "summary.csv", summary_rows)
    rate_rows = [
        {**row, "measure": measure, "rate": row[field]}
        for row in summary_rows
        for measure, field in (
            ("Expert hit rate", "hit_rate"),
            ("Minimum free", "minimum_free_rate"),
        )
    ]

    best = analysis["gate1"]["best_observed_tradeoff"]
    headline = [
        {
            "paired_median_gap": float(best["paired_median_gap"]),
            "gate_threshold": 0.15,
            "hit_rate_improvement": float(best["hit_rate_improvement"]),
            "minimum_free_drop_points": float(best["free_percent_drop"]),
            "admitted_rows": 30,
            "unique_output_hashes": 1,
        }
    ]
    source = source_spec()
    generated_at = str(admitted["created_at"])
    title = "ElasticUMA Gate 1: Expert-cache characterization on M1 Max"
    artifact = {
        "surface": "report",
        "manifest": {
            "version": 1,
            "surface": "report",
            "title": title,
            "description": "Technical result report for the preregistered ElasticUMA Gate-1 sweep.",
            "generatedAt": generated_at,
            "sources": [source],
            "cards": [
                {
                    "id": "paired-gap",
                    "description": "Median paired slowdown from 16 to 96 slots versus the frozen gate.",
                    "dataset": "headline",
                    "sourceId": "gate1-v4",
                    "metrics": [
                        {
                            "label": "Paired slowdown",
                            "field": "paired_median_gap",
                            "format": "percent",
                        },
                        {"label": "Gate", "field": "gate_threshold", "format": "percent"},
                    ],
                },
                {
                    "id": "hit-gain",
                    "description": "Expert hit-rate increase between the strongest compared arms.",
                    "dataset": "headline",
                    "sourceId": "gate1-v4",
                    "metrics": [
                        {
                            "label": "Hit-rate gain",
                            "field": "hit_rate_improvement",
                            "format": "percent",
                        }
                    ],
                },
                {
                    "id": "free-drop",
                    "description": "Drop in the median minimum system-free reading.",
                    "dataset": "headline",
                    "sourceId": "gate1-v4",
                    "metrics": [
                        {
                            "label": "Free-memory drop",
                            "field": "minimum_free_drop_points",
                            "format": "number",
                        }
                    ],
                },
                {
                    "id": "admission",
                    "description": "Every scheduled measured row was admitted with one deterministic output hash.",
                    "dataset": "headline",
                    "sourceId": "gate1-v4",
                    "metrics": [
                        {"label": "Admitted rows", "field": "admitted_rows", "format": "number"},
                        {
                            "label": "Output hashes",
                            "field": "unique_output_hashes",
                            "format": "number",
                        },
                    ],
                },
            ],
            "charts": [
                {
                    "id": "throughput-curve",
                    "title": "Decode throughput by expert-cache size",
                    "subtitle": "Six ordered cache sizes; medians from five admitted repetitions per arm",
                    "showDescription": True,
                    "intent": "trend",
                    "question": "How does decode throughput move as explicit expert-cache capacity increases?",
                    "rationale": "A line with visible ordered cache sizes shows the non-monotonic control curve.",
                    "comparisonContext": {
                        "baseline": "16-slot median",
                        "grain": "expert-cache arm",
                        "unit": "token/s",
                    },
                    "type": "line",
                    "dataset": "summary",
                    "sourceId": "gate1-v4",
                    "encodings": {
                        "x": {
                            "field": "expert_slots",
                            "type": "quantitative",
                            "label": "Expert-cache slots",
                        },
                        "y": {
                            "field": "median_decode_tps",
                            "type": "quantitative",
                            "label": "Median decode",
                            "unit": "token/s",
                        },
                        "tooltip": [
                            {"field": "cache_mib", "label": "Cache MiB"},
                            {"field": "hit_rate", "format": "percent", "label": "Hit rate"},
                            {
                                "field": "minimum_free_rate",
                                "format": "percent",
                                "label": "Minimum free",
                            },
                            {"field": "samples", "label": "Runs"},
                        ],
                    },
                    "xAxisTitle": "expert-cache slots",
                    "yAxisTitle": "median decode token/s",
                    "valueFormat": "number",
                    "unit": "token/s",
                    "layout": "full",
                    "palette": {"kind": "sequential", "name": "blue"},
                    "referenceLines": [
                        {
                            "axis": "y",
                            "color": "neutral",
                            "label": "15% gate",
                            "lineStyle": "dashed",
                            "value": float(summary_rows[0]["gate_threshold_tps"]),
                        }
                    ],
                    "settings": {"showPoints": "always"},
                    "surface": {"surface": "card", "showControls": False, "viewMode": "both"},
                },
                {
                    "id": "memory-curve",
                    "title": "Cache effectiveness and memory headroom",
                    "subtitle": "Hit rate rises while the minimum-free reading falls",
                    "showDescription": True,
                    "intent": "trend",
                    "question": "How do cache effectiveness and memory headroom co-move across cache sizes?",
                    "rationale": "Both measures are rates on a common zero-to-one scale and share the ordered cache axis.",
                    "comparisonContext": {
                        "denominator": "expert accesses for hit rate; system free percentage for headroom",
                        "grain": "expert-cache arm",
                        "unit": "rate",
                    },
                    "type": "line",
                    "dataset": "summary_rates",
                    "sourceId": "gate1-v4",
                    "encodings": {
                        "x": {
                            "field": "expert_slots",
                            "type": "quantitative",
                            "label": "Expert-cache slots",
                        },
                        "y": {
                            "field": "rate",
                            "type": "quantitative",
                            "format": "percent",
                        },
                        "color": {"field": "measure", "type": "nominal"},
                        "lineStyle": {"field": "measure", "type": "nominal"},
                        "tooltip": [
                            {
                                "field": "median_peak_compressor_growth_gib",
                                "label": "Peak compressor growth",
                                "unit": "GiB",
                            },
                            {
                                "field": "median_peak_swap_growth_mib",
                                "label": "Peak swap growth",
                                "unit": "MiB",
                            },
                        ],
                    },
                    "combinationRationale": "Both rate series share the same denominator scale and ordered cache-size grain.",
                    "xAxisTitle": "expert-cache slots",
                    "yAxisTitle": "rate",
                    "valueFormat": "percent",
                    "layout": "full",
                    "palette": {"kind": "categorical", "name": "hit-vs-headroom"},
                    "legend": {"position": "bottom", "sort": "spec", "title": "Measure"},
                    "referenceLines": [
                        {
                            "axis": "y",
                            "color": "neutral",
                            "label": "25% safety stop",
                            "lineStyle": "dashed",
                            "value": 0.25,
                        }
                    ],
                    "settings": {"showPoints": "always"},
                    "surface": {"surface": "card", "showControls": False, "viewMode": "both"},
                },
            ],
            "tables": [
                {
                    "id": "fixed-grid",
                    "title": "Fixed-policy summary",
                    "subtitle": "Medians across five admitted measured runs per cache arm",
                    "showDescription": True,
                    "dataset": "summary",
                    "defaultSort": {"field": "expert_slots", "direction": "asc"},
                    "density": "spacious",
                    "sourceId": "gate1-v4",
                    "layout": "full",
                    "columns": [
                        {"field": "expert_slots", "label": "Slots", "format": "number"},
                        {"field": "cache_mib", "label": "Cache MiB", "format": "number"},
                        {"field": "median_decode_tps", "label": "Decode tok/s", "format": "number"},
                        {"field": "hit_rate", "label": "Hit rate", "format": "percent"},
                        {"field": "minimum_free_rate", "label": "Min free", "format": "percent"},
                        {
                            "field": "median_peak_compressor_growth_gib",
                            "label": "Peak compressor GiB",
                            "format": "number",
                        },
                    ],
                }
            ],
            "blocks": [
                {"id": "title", "type": "markdown", "body": f"# {title}", "layout": "full"},
                {
                    "id": "summary-heading",
                    "type": "markdown",
                    "sourceId": "gate1-v4",
                    "body": (
                        "## Technical summary\n\nGate 1 is **NOT PROVEN**. All 30 measured rows "
                        "were admitted with identical outputs, but the strongest paired median slowdown "
                        "was 10.54%—below the frozen 15% controller-authorization threshold. The tested "
                        "expert-cache-only controller path is therefore stopped for this workload."
                    ),
                    "layout": "full",
                },
                {
                    "id": "headline-metrics",
                    "type": "metric-strip",
                    "cardIds": ["paired-gap", "hit-gain", "free-drop", "admission"],
                    "layout": "full",
                },
                {
                    "id": "throughput-finding",
                    "type": "markdown",
                    "sourceId": "gate1-v4",
                    "body": (
                        "## More cache improved hits but reduced speed\n\nThe 16-slot arm was the "
                        "fastest median configuration. Moving to 96 slots raised hit rate from 48.98% "
                        "to 90.13%, yet median decode fell from 11.330 to 10.120 token/s. The effect had "
                        "5/5 directional support, but its 8.94–10.84% bootstrap interval remains below "
                        "the preregistered gate."
                    ),
                    "layout": "full",
                },
                {
                    "id": "throughput-chart",
                    "type": "chart",
                    "chartId": "throughput-curve",
                    "layout": "full",
                },
                {
                    "id": "memory-finding",
                    "type": "markdown",
                    "sourceId": "gate1-v4",
                    "body": (
                        "## Memory headroom deteriorated before native warnings\n\nMedian minimum free "
                        "memory fell from 51% to 32%, while median peak compressor growth rose from "
                        "0.7 to 5.7 GiB. No admitted row produced a native warning or critical event, so "
                        "the polled free/compressor signals were materially earlier for this sweep."
                    ),
                    "layout": "full",
                },
                {
                    "id": "memory-chart",
                    "type": "chart",
                    "chartId": "memory-curve",
                    "layout": "full",
                },
                {"id": "summary-table", "type": "table", "tableId": "fixed-grid", "layout": "full"},
                {
                    "id": "definitions",
                    "type": "markdown",
                    "body": (
                        "## Scope and metric definitions\n\nThe population is one M1 Max/32 GB host, "
                        "one immutable Qwen3.6-35B-A3B Q4 checkpoint, one 60-token code prompt, batch "
                        "size one, a 4,096-token context limit, and 256 generated tokens. Decode token/s "
                        "and expert events come from the pinned native runtime. Memory values are sampled "
                        "at 0.5-second cadence; compressor growth is a peak above each row baseline."
                    ),
                    "layout": "full",
                },
                {
                    "id": "methodology",
                    "type": "markdown",
                    "body": (
                        "## Experimental design and validation\n\nOne forward warmup sweep was followed by "
                        "five measured sweeps alternating forward and reverse order. A process lock "
                        "prevented overlap. AC power, low-power mode off, thermal state, output parity, "
                        "free-memory and swap guards, recovery dwell, and native pressure events were "
                        "checked automatically. Failed v1–v3 safety/setup protocols remain preserved and "
                        "were not merged into v4."
                    ),
                    "layout": "full",
                },
                {
                    "id": "limitations",
                    "type": "markdown",
                    "body": (
                        "## The result is robust within a narrow scope\n\nFive paired repetitions and exact "
                        "output parity make the within-cell result credible, but one host/model/prompt "
                        "cannot establish generality. The bootstrap interval is descriptive for these "
                        "pairs, compressor association is not causal proof, token IDs were unavailable, "
                        "and energy/storage-byte measurements remain missing."
                    ),
                    "layout": "full",
                },
                {
                    "id": "next-steps",
                    "type": "markdown",
                    "body": (
                        "## Recommended next step: require an oracle that actually moves\n\nDo not build "
                        "the original expert-cache-only controller or lower its threshold. A successor "
                        "gate should vary workload phase, context/state, speculation, and controlled "
                        "co-tenancy, then show that the best safe configuration changes across held-out "
                        "cells. Only then should a joint controller be implemented and compared with the "
                        "best fixed fallback after transition cost."
                    ),
                    "layout": "full",
                },
                {
                    "id": "questions",
                    "type": "markdown",
                    "body": (
                        "## Further questions\n\n- Does the optimal cache move across prompt classes or context lengths?\n"
                        "- Can compressor/free derivatives predict one-time swap displacement before allocation?\n"
                        "- Does joint KV/MTP/cache control create a gap larger than any single control axis?\n"
                        "- Do Gemma 4 and newer M-series systems reproduce the same cache paradox?"
                    ),
                    "layout": "full",
                },
            ],
        },
        "snapshot": {
            "version": 1,
            "generatedAt": generated_at,
            "status": "ready",
            "datasets": {
                "headline": headline,
                "summary": summary_rows,
                "summary_rates": rate_rows,
                "measured": measured_rows,
            },
            "accessIssues": [],
        },
        "sources": [source],
    }
    atomic_write_json(output_dir / "artifact.json", artifact)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
