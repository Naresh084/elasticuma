from __future__ import annotations

import re
from typing import Any

FOOTER = re.compile(
    r"\[stop=(?P<stop>[^\s\]]+)\s+"
    r"prefill=(?P<prompt_tokens>\d+)tok/(?P<prefill_seconds>[0-9.]+)s\s+"
    r"new=(?P<completion_tokens>\d+)tok\s+"
    r"decode=(?P<decode_seconds>[0-9.]+)s\s+"
    r"tok/s=(?P<decode_tps>[0-9.]+)\]"
)
CACHE = re.compile(
    r"expert cache:\s+(?P<hit_percent>[0-9.]+)% hit,\s+"
    r"(?P<misses>\d+) miss(?:es)? of (?P<total>\d+)"
)
SPEC = re.compile(
    r"spec:\s+rounds (?P<rounds>\d+),\s+drafted (?P<drafted>\d+),\s+"
    r"accepted (?P<accepted_percent>[0-9.]+)%"
)
RESIDENCY = re.compile(
    r"\[expert-residency\s+hot_slots=(?P<hot_slots>\d+)\s+"
    r"volatile=(?P<volatile>\d+)\s+revalidate=(?P<revalidate>\d+)\s+"
    r"retained=(?P<retained>\d+)\s+empty=(?P<empty>\d+)\s+"
    r"discard=(?P<discard>\d+)\s+invalidated_slots=(?P<invalidated>\d+)\s+"
    r"reclaimed_bytes=(?P<reclaimed_bytes>\d+)\]"
)


def _exactly_one(pattern: re.Pattern[str], value: str, label: str) -> re.Match[str]:
    matches = list(pattern.finditer(value))
    if len(matches) != 1:
        raise ValueError(f"ambiguous runtime telemetry: {label} rows={len(matches)}")
    return matches[0]


def parse_slipstream_stderr(stderr: str) -> dict[str, Any]:
    """Parse the pinned CLI's stable phase footer and cache receipt.

    Required records fail closed if absent or duplicated. Speculation telemetry
    is optional because autoregressive runs legitimately omit it.
    """

    footer = _exactly_one(FOOTER, stderr, "footer").groupdict()
    cache = _exactly_one(CACHE, stderr, "expert-cache").groupdict()
    prompt_tokens = int(footer["prompt_tokens"])
    completion_tokens = int(footer["completion_tokens"])
    prefill_seconds = float(footer["prefill_seconds"])
    misses = int(cache["misses"])
    accesses = int(cache["total"])
    calculated_hit_rate = (accesses - misses) / accesses if accesses else 0.0
    reported_hit_rate = float(cache["hit_percent"]) / 100
    if abs(calculated_hit_rate - reported_hit_rate) > 0.001:
        raise ValueError("runtime expert hit percentage disagrees with hit/miss counts")
    result: dict[str, Any] = {
        "stop_reason": footer["stop"],
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "prompt_tps": prompt_tokens / prefill_seconds if prefill_seconds else 0.0,
        "decode_tps": float(footer["decode_tps"]),
        "decode_seconds": float(footer["decode_seconds"]),
        "prefill_seconds": prefill_seconds,
        "expert_hit_rate": calculated_hit_rate,
        "expert_miss_count": misses,
        "expert_access_count": accesses,
        "runtime_reported_hit_rate": reported_hit_rate,
    }
    spec_rows = list(SPEC.finditer(stderr))
    if len(spec_rows) > 1:
        raise ValueError(f"ambiguous runtime telemetry: speculation rows={len(spec_rows)}")
    if spec_rows:
        spec = spec_rows[0].groupdict()
        drafted = int(spec["drafted"])
        result["mtp_drafted_tokens"] = drafted
        result["mtp_accepted_tokens"] = round(drafted * float(spec["accepted_percent"]) / 100)
    residency_rows = list(RESIDENCY.finditer(stderr))
    if len(residency_rows) > 1:
        raise ValueError(
            f"ambiguous runtime telemetry: expert-residency rows={len(residency_rows)}"
        )
    if residency_rows:
        residency = residency_rows[0].groupdict()
        result.update(
            {
                "expert_residency_hot_slots": int(residency["hot_slots"]),
                "expert_volatile_transitions": int(residency["volatile"]),
                "expert_residency_revalidations": int(residency["revalidate"]),
                "expert_retained_revalidations": int(residency["retained"]),
                "expert_empty_recoveries": int(residency["empty"]),
                "expert_explicit_discards": int(residency["discard"]),
                "expert_residency_invalidated_slots": int(residency["invalidated"]),
                "expert_reclaimed_bytes": int(residency["reclaimed_bytes"]),
            }
        )
    return result
