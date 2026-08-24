from __future__ import annotations

import pytest

from elasticuma.slipstream import parse_slipstream_stderr


def test_parser_extracts_required_cache_and_phase_receipts() -> None:
    stderr = (
        "phase decode\n"
        "expert cache: 75.0% hit, 10 misses of 40\n"
        "[expert-residency hot_slots=16 volatile=30 revalidate=20 retained=12 "
        "empty=8 discard=0 invalidated_slots=7 reclaimed_bytes=123456]\n"
        "[stop=length prefill=128tok/2.000s new=32tok decode=4.000s tok/s=8.00]\n"
    )
    result = parse_slipstream_stderr(stderr)
    assert result["prompt_tokens"] == 128
    assert result["completion_tokens"] == 32
    assert result["prompt_tps"] == 64.0
    assert result["decode_tps"] == 8.0
    assert result["expert_hit_rate"] == 0.75
    assert result["expert_miss_count"] == 10
    assert result["expert_access_count"] == 40
    assert result["expert_residency_hot_slots"] == 16
    assert result["expert_empty_recoveries"] == 8
    assert result["expert_reclaimed_bytes"] == 123456


def test_parser_fails_closed_on_duplicate_telemetry() -> None:
    footer = "[stop=length prefill=1tok/1.0s new=1tok decode=1.0s tok/s=1.0]"
    stderr = f"expert cache: 0% hit, 1 miss of 1\n{footer}\n{footer}\n"
    with pytest.raises(ValueError, match="footer rows=2"):
        parse_slipstream_stderr(stderr)


def test_parser_rejects_internally_inconsistent_cache_receipt() -> None:
    stderr = """
expert cache: 80.0% hit, 10 misses of 40
[stop=maxTokens prefill=1tok/1.0s new=1tok decode=1.0s tok/s=1.0]
"""
    with pytest.raises(ValueError, match="disagrees"):
        parse_slipstream_stderr(stderr)
