#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
import statistics
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

BLUE = "#2563EB"
GOLD = "#D97706"
ORANGE = "#C2410C"
OLIVE = "#4D7C0F"
DARK = "#1F2937"
GRAY = "#9CA3AF"
GRID = "#E5E7EB"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-stem", type=Path, required=True)
    return parser.parse_args()


def bootstrap_median(values: list[float], *, draws: int = 10_000) -> tuple[float, float]:
    generator = random.Random(104729)
    medians = sorted(
        statistics.median(generator.choices(values, k=len(values))) for _ in range(draws)
    )
    return medians[int(0.025 * (draws - 1))], medians[int(0.975 * (draws - 1))]


def minimum_free(record: dict[str, object]) -> float:
    snapshots = [record["memory_before"], *record["memory_samples"], record["memory_after"]]
    return min(float(snapshot["free_percent"]) for snapshot in snapshots)


def peak_compressor_gib(record: dict[str, object]) -> float:
    before = record["memory_before"]
    snapshots = [before, *record["memory_samples"], record["memory_after"]]
    peak_pages = max(int(snapshot["pages_compressor"]) for snapshot in snapshots)
    growth = max(0, peak_pages - int(before["pages_compressor"]))
    return growth * int(before["page_size"]) / 1024**3


def main() -> int:
    args = parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    if payload.get("complete") is not True:
        raise SystemExit("plot requires a complete admitted experiment")
    records = payload.get("records")
    if not isinstance(records, list) or len(records) != 30:
        raise SystemExit("plot expects the 30-row admitted Gate-1 v4 dataset")
    groups: dict[int, list[dict[str, object]]] = defaultdict(list)
    for record in records:
        slots = int(record["runtime"]["expert_cache_slots"])
        groups[slots].append(record)
    slots = sorted(groups)
    if slots != [16, 24, 32, 48, 64, 96] or any(len(groups[value]) != 5 for value in slots):
        raise SystemExit("unexpected Gate-1 cache grid")

    throughput = [[float(row["runtime"]["decode_tps"]) for row in groups[value]] for value in slots]
    medians = [statistics.median(values) for values in throughput]
    intervals = [bootstrap_median(values) for values in throughput]
    hit_rates = [
        statistics.median(float(row["runtime"]["expert_hit_rate"]) for row in groups[value])
        for value in slots
    ]
    free_values = [[minimum_free(row) for row in groups[value]] for value in slots]
    free_medians = [statistics.median(values) for values in free_values]
    compressor_values = [[peak_compressor_gib(row) for row in groups[value]] for value in slots]
    compressor_medians = [statistics.median(values) for values in compressor_values]

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.titlesize": 11,
            "axes.labelsize": 9,
            "axes.edgecolor": DARK,
            "axes.labelcolor": DARK,
            "xtick.color": DARK,
            "ytick.color": DARK,
            "text.color": DARK,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
        }
    )
    figure, axes = plt.subplots(2, 2, figsize=(10.5, 7.5))
    figure.subplots_adjust(left=0.08, right=0.98, bottom=0.08, top=0.84, hspace=0.38, wspace=0.20)
    figure.suptitle(
        "Gate 1 fixed expert-cache sweep on M1 Max",
        fontsize=15,
        x=0.05,
        y=0.975,
        ha="left",
    )
    figure.text(
        0.05,
        0.935,
        "Qwen3.6-35B-A3B Q4 · AC power · n=5 admitted runs per arm · identical outputs",
        fontsize=9,
        color="#4B5563",
        ha="left",
    )

    axis = axes[0, 0]
    for index, values in enumerate(throughput):
        axis.scatter([slots[index]] * len(values), values, color=GRAY, s=18, alpha=0.65, zorder=2)
    lower = [median - interval[0] for median, interval in zip(medians, intervals, strict=True)]
    upper = [interval[1] - median for median, interval in zip(medians, intervals, strict=True)]
    axis.errorbar(
        slots,
        medians,
        yerr=[lower, upper],
        color=BLUE,
        marker="o",
        linewidth=2,
        capsize=3,
        zorder=3,
    )
    threshold = medians[0] * 0.85
    axis.axhline(threshold, color=DARK, linestyle="--", linewidth=1.2)
    axis.text(96, threshold + 0.03, "15% gate", ha="right", va="bottom", fontsize=8)
    axis.set_title("Decode throughput")
    axis.set_ylabel("token/s")
    axis.set_ylim(9.5, 11.75)
    axis.text(
        0.02,
        0.96,
        "dots: runs · bars: bootstrap 95% interval",
        transform=axis.transAxes,
        fontsize=8,
        color="#4B5563",
        va="top",
    )
    gap = (medians[0] - medians[-1]) / medians[0]
    axis.annotate(
        f"Observed gap {gap:.1%}\nNOT PROVEN",
        xy=(96, medians[-1]),
        xytext=(62, 9.82),
        arrowprops={"arrowstyle": "->", "color": DARK},
        fontsize=8,
        ha="center",
    )

    axis = axes[0, 1]
    axis.plot(slots, hit_rates, color=GOLD, marker="s", linewidth=2)
    for x, value in zip(slots, hit_rates, strict=True):
        axis.text(x, value + 0.018, f"{value:.0%}", ha="center", fontsize=8)
    axis.set_title("Expert-cache hit rate")
    axis.set_ylabel("hit rate")
    axis.set_ylim(0, 1)
    axis.yaxis.set_major_formatter(PercentFormatter(1.0))

    axis = axes[1, 0]
    for index, values in enumerate(free_values):
        axis.scatter([slots[index]] * len(values), values, color=GRAY, s=18, alpha=0.65)
    axis.plot(slots, free_medians, color=ORANGE, marker="^", linewidth=2)
    axis.axhline(25, color=DARK, linestyle="--", linewidth=1.2)
    axis.text(96, 26, "25% safety stop", ha="right", va="bottom", fontsize=8)
    axis.set_title("Minimum system-free reading")
    axis.set_ylabel("free memory (%)")
    axis.set_ylim(0, 65)

    axis = axes[1, 1]
    axis.bar(slots, compressor_medians, width=5.5, color="#D9E7C5", edgecolor=OLIVE)
    axis.plot(slots, compressor_medians, color=OLIVE, marker="D", linewidth=1.5)
    for x, value in zip(slots, compressor_medians, strict=True):
        axis.text(x, value + 0.14, f"{value:.1f}", ha="center", fontsize=8)
    axis.set_title("Peak compressor growth")
    axis.set_ylabel("GiB above row baseline")
    axis.set_ylim(0, max(compressor_medians) * 1.2)

    for axis in axes.flat:
        axis.set_xlabel("expert-cache slots")
        axis.set_xticks(slots)
        axis.grid(axis="y", color=GRID, linewidth=0.8)
        axis.spines["top"].set_visible(False)
        axis.spines["right"].set_visible(False)

    args.output_stem.parent.mkdir(parents=True, exist_ok=True)
    metadata = {
        "Title": "Gate 1 fixed expert-cache sweep on M1 Max",
        "Description": "ElasticUMA admitted Gate-1 v4 evidence",
        "Source": "ElasticUMA",
    }
    svg_path = args.output_stem.with_suffix(".svg")
    figure.savefig(svg_path, metadata=metadata)
    svg = svg_path.read_text(encoding="utf-8")
    svg_path.write_text(
        "\n".join(line.rstrip() for line in svg.splitlines()) + "\n", encoding="utf-8"
    )
    figure.savefig(args.output_stem.with_suffix(".png"), dpi=220, metadata=metadata)
    plt.close(figure)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
