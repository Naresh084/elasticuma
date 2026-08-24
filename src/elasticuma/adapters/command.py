from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from elasticuma.schema import RuntimeResult
from elasticuma.util import sha256_text

from .base import RuntimeAdapter

RESULT_PREFIX = "ELASTICUMA_RESULT="


def _number(payload: dict[str, Any], key: str, kind: type[int] | type[float]) -> Any:
    value = payload.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"runtime field {key!r} is not numeric")
    return kind(value)


class CommandResultAdapter(RuntimeAdapter):
    def _load_payload(self, stdout_path: Path, result_path: Path) -> dict[str, Any]:
        if result_path.is_file():
            with result_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if not isinstance(payload, dict):
                raise ValueError("runtime result file must contain a JSON object")
            return payload
        candidates: list[str] = []
        with stdout_path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if line.startswith(RESULT_PREFIX):
                    candidates.append(line[len(RESULT_PREFIX) :].strip())
        if len(candidates) != 1:
            raise ValueError(f"expected one {RESULT_PREFIX!r} line, found {len(candidates)}")
        payload = json.loads(candidates[0])
        if not isinstance(payload, dict):
            raise ValueError("runtime result line must contain a JSON object")
        return payload

    def parse(self, *, stdout_path: Path, stderr_path: Path, result_path: Path) -> RuntimeResult:
        del stderr_path
        payload = self._load_payload(stdout_path, result_path)
        text = payload.get("text")
        tokens = payload.get("token_ids")
        output_hash = payload.get("output_sha256")
        token_hash = payload.get("token_ids_sha256")
        if output_hash is None and isinstance(text, str):
            output_hash = sha256_text(text)
        if token_hash is None and isinstance(tokens, list):
            if not all(isinstance(item, int) and not isinstance(item, bool) for item in tokens):
                raise ValueError("token_ids must contain only integers")
            token_hash = sha256_text(json.dumps(tokens, separators=(",", ":")))
        return RuntimeResult(
            prompt_tokens=_number(payload, "prompt_tokens", int),
            completion_tokens=_number(payload, "completion_tokens", int),
            prompt_tps=_number(payload, "prompt_tps", float),
            decode_tps=_number(payload, "decode_tps", float),
            ttft_seconds=_number(payload, "ttft_seconds", float),
            output_sha256=str(output_hash) if output_hash else None,
            token_ids_sha256=str(token_hash) if token_hash else None,
            expert_hit_rate=_number(payload, "expert_hit_rate", float),
            expert_miss_count=_number(payload, "expert_miss_count", int),
            expert_access_count=_number(payload, "expert_access_count", int),
            expert_cache_slots=_number(payload, "expert_cache_slots", int),
            expert_miss_bytes=_number(payload, "expert_miss_bytes", int),
            expert_materialized_bytes=_number(payload, "expert_materialized_bytes", int),
            expert_evictions=_number(payload, "expert_evictions", int),
            mtp_drafted_tokens=_number(payload, "mtp_drafted_tokens", int),
            mtp_accepted_tokens=_number(payload, "mtp_accepted_tokens", int),
            expert_residency_hot_slots=_number(payload, "expert_residency_hot_slots", int),
            expert_volatile_transitions=_number(payload, "expert_volatile_transitions", int),
            expert_residency_revalidations=_number(payload, "expert_residency_revalidations", int),
            expert_retained_revalidations=_number(payload, "expert_retained_revalidations", int),
            expert_empty_recoveries=_number(payload, "expert_empty_recoveries", int),
            expert_explicit_discards=_number(payload, "expert_explicit_discards", int),
            expert_residency_invalidated_slots=_number(
                payload, "expert_residency_invalidated_slots", int
            ),
            expert_reclaimed_bytes=_number(payload, "expert_reclaimed_bytes", int),
            runtime_payload=payload,
        )
