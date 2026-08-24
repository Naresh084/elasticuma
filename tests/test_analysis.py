from __future__ import annotations

from elasticuma.analysis import gate1_verdict, purgeable_comparison, summarize


def test_gate1_requires_hit_gain_throughput_loss_and_pressure_evidence() -> None:
    summary = [
        {
            "arm_name": "small",
            "cache_mib": 2048,
            "pressure_mib": 0,
            "median_decode_tps": 20.0,
            "median_expert_hit_rate": 0.60,
            "median_min_free_percent": 30.0,
            "median_compressor_delta_bytes": 0,
            "median_swap_delta_bytes": 0,
        },
        {
            "arm_name": "large",
            "cache_mib": 8192,
            "pressure_mib": 0,
            "median_decode_tps": 16.0,
            "median_expert_hit_rate": 0.90,
            "median_min_free_percent": 24.0,
            "median_compressor_delta_bytes": 512 * 1024**2,
            "median_swap_delta_bytes": 0,
        },
    ]
    verdict = gate1_verdict(summary)
    assert verdict["passed"] is True
    assert verdict["candidate_count"] == 1


def test_gate1_does_not_pass_on_speed_loss_without_hit_gain() -> None:
    summary = [
        {
            "arm_name": "small",
            "cache_mib": 2048,
            "pressure_mib": 0,
            "median_decode_tps": 20.0,
            "median_expert_hit_rate": 0.8,
            "median_min_free_percent": 30.0,
        },
        {
            "arm_name": "large",
            "cache_mib": 8192,
            "pressure_mib": 0,
            "median_decode_tps": 15.0,
            "median_expert_hit_rate": 0.7,
            "median_min_free_percent": 20.0,
        },
    ]
    assert gate1_verdict(summary)["passed"] is False


def test_summary_keeps_transient_peak_compression() -> None:
    record = {
        "arm_name": "cache",
        "cache_mib": 1024,
        "pressure_mib": 0,
        "runtime": {"decode_tps": 10.0, "expert_hit_rate": 0.5},
        "memory_before": {
            "free_percent": 40.0,
            "page_size": 16384,
            "pages_compressor": 100,
            "swap_used_bytes": 0,
            "pressure_level": "normal",
        },
        "memory_samples": [
            {
                "free_percent": 20.0,
                "page_size": 16384,
                "pages_compressor": 1000,
                "swap_used_bytes": 1024,
                "pressure_level": "warning",
            }
        ],
        "memory_after": {
            "free_percent": 35.0,
            "page_size": 16384,
            "pages_compressor": 100,
            "swap_used_bytes": 0,
            "pressure_level": "normal",
        },
        "process_samples": [{"rss_bytes": 1234, "phys_footprint_bytes": 987}],
    }
    row = summarize([record])[0]
    assert row["median_peak_compressor_growth_bytes"] == 900 * 16384
    assert row["median_peak_swap_growth_bytes"] == 1024
    assert row["median_peak_pressure_score"] == 1.0
    assert row["median_peak_process_rss_bytes"] == 1234
    assert row["median_peak_process_phys_footprint_bytes"] == 987


def test_gate1_with_records_requires_repeated_paired_support() -> None:
    summary = [
        {
            "arm_name": "small",
            "cache_mib": 1000,
            "pressure_mib": 0,
            "median_decode_tps": 20.0,
            "median_expert_hit_rate": 0.5,
            "median_min_free_percent": 40.0,
            "median_peak_compressor_growth_bytes": 0,
        },
        {
            "arm_name": "large",
            "cache_mib": 2000,
            "pressure_mib": 0,
            "median_decode_tps": 16.0,
            "median_expert_hit_rate": 0.8,
            "median_min_free_percent": 35.0,
            "median_peak_compressor_growth_bytes": 512 * 1024**2,
        },
    ]
    records = []
    for repetition in range(5):
        records.extend(
            [
                {
                    "arm_name": "small",
                    "repetition": repetition,
                    "runtime": {"decode_tps": 20.0},
                },
                {
                    "arm_name": "large",
                    "repetition": repetition,
                    "runtime": {"decode_tps": 16.0},
                },
            ]
        )
    candidate = gate1_verdict(summary, records)["candidates"][0]
    assert candidate["paired_repetitions"] == 5
    assert candidate["paired_directional_support"] == 5
    assert candidate["paired_median_gap"] == 0.2


def test_purgeable_comparison_reports_paired_gain_and_footprint_reduction() -> None:
    records = []
    for repetition in range(5):
        for arm, tps, hit, footprint, empty in (
            ("baseline", 10.0, 0.5, 1000, None),
            ("candidate", 12.0, 0.8, 700, 4),
        ):
            records.append(
                {
                    "arm_name": arm,
                    "repetition": repetition,
                    "cache_mib": 100,
                    "pressure_mib": 0,
                    "runtime": {
                        "decode_tps": tps,
                        "expert_hit_rate": hit,
                        "expert_empty_recoveries": empty,
                        "expert_reclaimed_bytes": 123 if empty else None,
                    },
                    "memory_before": {
                        "free_percent": 50,
                        "page_size": 1,
                        "pages_compressor": 0,
                        "swap_used_bytes": 0,
                        "pressure_level": "normal",
                    },
                    "memory_samples": [],
                    "memory_after": {
                        "free_percent": 50,
                        "page_size": 1,
                        "pages_compressor": 0,
                        "swap_used_bytes": 0,
                        "pressure_level": "normal",
                    },
                    "process_samples": [
                        {"rss_bytes": footprint, "phys_footprint_bytes": footprint}
                    ],
                }
            )
    result = purgeable_comparison(
        records,
        candidate_arm="candidate",
        baseline_arms=["baseline"],
    )
    comparison = result["comparisons"][0]
    assert round(comparison["paired_median_candidate_gain"], 10) == 0.2
    assert comparison["peak_phys_footprint_reduction"] == 0.3
    assert result["candidate_empty_recoveries"] == [4.0] * 5
