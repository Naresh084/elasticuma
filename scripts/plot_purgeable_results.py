#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
import statistics
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import PercentFormatter

INK = "#111827"
MUTED = "#475569"
SOFT = "#64748B"
NAVY = "#1F4E79"
BLUE = "#1D4ED8"
LIGHT = "#CBD5E1"
SURFACE = "#F1F5F9"
GRID = "#E2E8F0"

POLICIES = ("Upstream 16", "Upstream 96", "ElasticUMA 96/hot16")
COLORS = (LIGHT, SOFT, NAVY)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pressure", type=Path, required=True)
    parser.add_argument("--no-pressure", type=Path, required=True)
    parser.add_argument("--gemma", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def load_records(path: Path) -> list[dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = payload.get("records")
    if payload.get("complete") is not True or not isinstance(records, list) or len(records) != 15:
        raise ValueError(f"expected a complete 15-row admitted experiment: {path}")
    return records


def policy_name(arm: str) -> str:
    if "fixed-16" in arm:
        return "Upstream 16"
    if "fixed-96" in arm:
        return "Upstream 96"
    if "elasticuma" in arm:
        return "ElasticUMA 96/hot16"
    raise ValueError(f"unknown arm: {arm}")


def peak_footprint_gib(record: dict[str, object]) -> float:
    values = [
        int(sample["phys_footprint_bytes"])
        for sample in record["process_samples"]
        if sample.get("phys_footprint_bytes") is not None
    ]
    return max(values) / 1024**3


def grouped(records: list[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    result: dict[str, list[dict[str, object]]] = defaultdict(list)
    for record in records:
        result[policy_name(str(record["arm_name"]))].append(record)
    if set(result) != set(POLICIES) or any(len(result[name]) != 5 for name in POLICIES):
        raise ValueError("unexpected policy groups")
    return result


def bootstrap_median(values: list[float]) -> tuple[float, float]:
    generator = random.Random(104729)
    medians = sorted(
        statistics.median(generator.choices(values, k=len(values))) for _ in range(10_000)
    )
    return medians[249], medians[9749]


def configure_plotting() -> None:
    plt.rcParams.update(
        {
            "font.family": "Arial",
            "font.size": 9,
            "axes.titlesize": 11,
            "axes.labelsize": 9,
            "axes.edgecolor": INK,
            "axes.labelcolor": INK,
            "xtick.color": INK,
            "ytick.color": INK,
            "text.color": INK,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "svg.hashsalt": "elasticuma-ieee-2026-08-24",
        }
    )


def save_figure_pair(
    figure: plt.Figure,
    output_dir: Path,
    stem: str,
    metadata: dict[str, str],
) -> None:
    svg_metadata = {**metadata, "Date": "2026-08-24"}
    figure.savefig(output_dir / f"{stem}.svg", metadata=svg_metadata)
    figure.savefig(output_dir / f"{stem}.png", dpi=240, metadata=metadata)


def main_results(
    pressure: dict[str, list[dict[str, object]]],
    no_pressure: dict[str, list[dict[str, object]]],
    output_dir: Path,
) -> None:
    conditions = ("4 GiB co-tenant", "No synthetic pressure")
    datasets = (pressure, no_pressure)
    x = np.arange(len(conditions))
    width = 0.23
    figure, axes = plt.subplots(1, 2, figsize=(11.8, 4.7))
    figure.subplots_adjust(left=0.07, right=0.985, bottom=0.19, top=0.78, wspace=0.24)
    figure.suptitle(
        "Committed ElasticUMA versus untouched upstream fixed caches",
        x=0.04,
        y=0.965,
        ha="left",
        fontsize=15,
        fontweight="bold",
    )
    figure.text(
        0.04,
        0.905,
        "M1 Max · Qwen3.6-35B-A3B Q4 · n=5 admitted runs per arm · "
        "identical outputs within each protocol",
        ha="left",
        fontsize=9,
        color=MUTED,
    )

    for policy_index, (policy, color) in enumerate(zip(POLICIES, COLORS, strict=True)):
        offset = (policy_index - 1) * width
        decode_values = [
            [float(row["runtime"]["decode_tps"]) for row in dataset[policy]] for dataset in datasets
        ]
        decode_medians = [statistics.median(values) for values in decode_values]
        bars = axes[0].bar(
            x + offset,
            decode_medians,
            width,
            label=policy,
            color=color,
            edgecolor=INK if policy != "ElasticUMA 96/hot16" else NAVY,
            linewidth=0.8,
        )
        for condition_index, values in enumerate(decode_values):
            jitter = np.linspace(-0.065, 0.065, len(values))
            axes[0].scatter(
                np.full(len(values), x[condition_index] + offset) + jitter,
                values,
                s=13,
                color="white" if policy == "ElasticUMA 96/hot16" else INK,
                edgecolor=INK,
                linewidth=0.55,
                zorder=3,
            )
        axes[0].bar_label(bars, labels=[f"{value:.2f}" for value in decode_medians], padding=3)

        footprint_values = [
            [peak_footprint_gib(row) for row in dataset[policy]] for dataset in datasets
        ]
        footprint_medians = [statistics.median(values) for values in footprint_values]
        bars = axes[1].bar(
            x + offset,
            footprint_medians,
            width,
            color=color,
            edgecolor=INK if policy != "ElasticUMA 96/hot16" else NAVY,
            linewidth=0.8,
        )
        for condition_index, values in enumerate(footprint_values):
            jitter = np.linspace(-0.065, 0.065, len(values))
            axes[1].scatter(
                np.full(len(values), x[condition_index] + offset) + jitter,
                values,
                s=13,
                color="white" if policy == "ElasticUMA 96/hot16" else INK,
                edgecolor=INK,
                linewidth=0.55,
                zorder=3,
            )
        axes[1].bar_label(bars, labels=[f"{value:.2f}" for value in footprint_medians], padding=3)

    axes[0].set_title("(a) Decode throughput")
    axes[0].set_ylabel("token/s (higher is better)")
    axes[0].set_ylim(0, 20)
    axes[1].set_title("(b) Peak physical footprint")
    axes[1].set_ylabel("GiB (lower is better)")
    axes[1].set_ylim(0, 8)
    for axis in axes:
        axis.set_xticks(x, conditions)
        axis.grid(axis="y", color=GRID, linewidth=0.8)
        axis.set_axisbelow(True)
        axis.spines["top"].set_visible(False)
        axis.spines["right"].set_visible(False)
    handles, labels = axes[0].get_legend_handles_labels()
    figure.legend(handles, labels, loc="upper right", bbox_to_anchor=(0.985, 0.96), frameon=False)
    figure.text(
        0.04,
        0.04,
        "Bars show medians; dots show all measured runs. Source: admitted V6/V7 receipts.",
        fontsize=8,
        color=MUTED,
    )
    metadata = {
        "Title": "ElasticUMA main results",
        "Description": "Admitted V6 and V7 throughput and physical-footprint medians",
        "Source": "ElasticUMA",
    }
    save_figure_pair(figure, output_dir, "elasticuma-main-results", metadata)
    plt.close(figure)


def paired_gains(
    pressure: dict[str, list[dict[str, object]]],
    no_pressure: dict[str, list[dict[str, object]]],
    output_dir: Path,
) -> None:
    rows = [
        ("4 GiB co-tenant · vs upstream 16", pressure, "Upstream 16"),
        ("4 GiB co-tenant · vs upstream 96", pressure, "Upstream 96"),
        ("No pressure · vs upstream 16", no_pressure, "Upstream 16"),
        ("No pressure · vs upstream 96", no_pressure, "Upstream 96"),
    ]
    figure, axis = plt.subplots(figsize=(10.2, 4.7))
    figure.subplots_adjust(left=0.33, right=0.97, top=0.76, bottom=0.18)
    figure.suptitle(
        "Paired decode throughput gain by protocol and baseline",
        x=0.04,
        y=0.965,
        ha="left",
        fontsize=15,
        fontweight="bold",
    )
    figure.text(
        0.04,
        0.90,
        "Candidate gain = (ElasticUMA - upstream) / upstream; five same-repetition pairs per row",
        ha="left",
        fontsize=9,
        color=MUTED,
    )

    for row_index, (label, dataset, baseline) in enumerate(rows):
        candidate_by_rep = {
            int(item["repetition"]): float(item["runtime"]["decode_tps"])
            for item in dataset["ElasticUMA 96/hot16"]
        }
        baseline_by_rep = {
            int(item["repetition"]): float(item["runtime"]["decode_tps"])
            for item in dataset[baseline]
        }
        gains = [
            candidate_by_rep[index] / baseline_by_rep[index] - 1
            for index in sorted(candidate_by_rep)
        ]
        median = statistics.median(gains)
        lower, upper = bootstrap_median(gains)
        y = len(rows) - 1 - row_index
        axis.scatter(gains, [y] * len(gains), color=SOFT, s=28, alpha=0.75, zorder=2)
        axis.plot([lower, upper], [y, y], color=NAVY, linewidth=4, solid_capstyle="round")
        axis.scatter([median], [y], color=BLUE, edgecolor=INK, marker="D", s=55, zorder=3)
        axis.text(upper + 0.015, y, f"median {median:.1%}", va="center", fontsize=8.5)
        axis.text(-0.02, y + 0.26, label, ha="right", va="center", fontsize=9)

    axis.axvline(0, color=INK, linewidth=1.1)
    axis.axvspan(-0.10, 0, color=SURFACE, zorder=0)
    axis.text(-0.095, 3.58, "candidate slower", fontsize=8, color=MUTED, va="bottom")
    axis.text(0.01, 3.58, "candidate faster", fontsize=8, color=NAVY, va="bottom")
    axis.set_yticks([])
    axis.set_xlim(-0.11, 0.47)
    axis.set_ylim(-0.55, 3.75)
    axis.xaxis.set_major_formatter(PercentFormatter(1.0))
    axis.set_xlabel("paired decode throughput gain")
    axis.grid(axis="x", color=GRID, linewidth=0.8)
    axis.set_axisbelow(True)
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    axis.spines["left"].set_visible(False)
    figure.text(
        0.04,
        0.04,
        "Dots: measured pairs · diamond: median · navy interval: "
        "deterministic bootstrap 95% interval.",
        fontsize=8,
        color=MUTED,
    )
    metadata = {
        "Title": "ElasticUMA paired throughput gains",
        "Description": "Five paired candidate gains against upstream fixed baselines",
        "Source": "ElasticUMA",
    }
    save_figure_pair(figure, output_dir, "elasticuma-paired-gains", metadata)
    plt.close(figure)


def cross_model(
    qwen: dict[str, list[dict[str, object]]],
    gemma: dict[str, list[dict[str, object]]],
    output_dir: Path,
) -> None:
    models = ("Qwen3.6 35B-A3B", "Gemma 4 26B-A4B")
    datasets = (qwen, gemma)
    x = np.arange(len(models))
    width = 0.23
    figure, axes = plt.subplots(1, 2, figsize=(11.8, 4.7))
    figure.subplots_adjust(left=0.07, right=0.985, bottom=0.19, top=0.78, wspace=0.24)
    figure.suptitle(
        "No-pressure result across two MoE architectures",
        x=0.04,
        y=0.965,
        ha="left",
        fontsize=15,
        fontweight="bold",
    )
    figure.text(
        0.04,
        0.905,
        "M1 Max · n=5 admitted runs per arm · model-specific unseen prompts · exact outputs",
        ha="left",
        fontsize=9,
        color=MUTED,
    )
    for policy_index, (policy, color) in enumerate(zip(POLICIES, COLORS, strict=True)):
        offset = (policy_index - 1) * width
        decode_values = [
            [float(row["runtime"]["decode_tps"]) for row in dataset[policy]] for dataset in datasets
        ]
        medians = [statistics.median(values) for values in decode_values]
        bars = axes[0].bar(
            x + offset,
            medians,
            width,
            label=policy,
            color=color,
            edgecolor=INK if policy != "ElasticUMA 96/hot16" else NAVY,
            linewidth=0.8,
        )
        axes[0].bar_label(bars, labels=[f"{value:.2f}" for value in medians], padding=3)
        footprint_values = [
            [peak_footprint_gib(row) for row in dataset[policy]] for dataset in datasets
        ]
        medians = [statistics.median(values) for values in footprint_values]
        bars = axes[1].bar(
            x + offset,
            medians,
            width,
            color=color,
            edgecolor=INK if policy != "ElasticUMA 96/hot16" else NAVY,
            linewidth=0.8,
        )
        axes[1].bar_label(bars, labels=[f"{value:.2f}" for value in medians], padding=3)
    axes[0].set_title("(a) Decode throughput")
    axes[0].set_ylabel("token/s (higher is better)")
    axes[0].set_ylim(0, 28)
    axes[1].set_title("(b) Peak physical footprint")
    axes[1].set_ylabel("GiB (lower is better)")
    axes[1].set_ylim(0, 10)
    for axis in axes:
        axis.set_xticks(x, models)
        axis.grid(axis="y", color=GRID, linewidth=0.8)
        axis.set_axisbelow(True)
        axis.spines["top"].set_visible(False)
        axis.spines["right"].set_visible(False)
    handles, labels = axes[0].get_legend_handles_labels()
    figure.legend(handles, labels, loc="upper right", bbox_to_anchor=(0.985, 0.96), frameon=False)
    figure.text(
        0.04,
        0.04,
        "Bars show medians. Qwen uses 256 generated tokens; Gemma uses 128.",
        fontsize=8,
        color=MUTED,
    )
    metadata = {
        "Title": "ElasticUMA cross-model result",
        "Description": "Admitted Qwen3.6 and Gemma 4 throughput and footprint medians",
        "Source": "ElasticUMA",
    }
    save_figure_pair(figure, output_dir, "elasticuma-cross-model", metadata)
    plt.close(figure)


def main() -> int:
    args = parse_args()
    configure_plotting()
    pressure = grouped(load_records(args.pressure))
    no_pressure = grouped(load_records(args.no_pressure))
    gemma = grouped(load_records(args.gemma))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    main_results(pressure, no_pressure, args.output_dir)
    paired_gains(pressure, no_pressure, args.output_dir)
    cross_model(no_pressure, gemma, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
