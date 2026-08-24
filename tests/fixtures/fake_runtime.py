from __future__ import annotations

import argparse
import json
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--cache-mib", type=int, required=True)
    parser.add_argument("--sleep", type=float, default=0.05)
    args = parser.parse_args()
    time.sleep(args.sleep)
    payload = {
        "prompt_tokens": 32,
        "completion_tokens": 16,
        "prompt_tps": 100.0,
        "decode_tps": 20.0 - max(0, args.cache_mib - 2048) / 1024,
        "ttft_seconds": 0.32,
        "text": "deterministic fixture output",
        "token_ids": [1, 2, 3, 4],
        "expert_hit_rate": min(0.99, 0.5 + args.cache_mib / 16384),
        "expert_miss_bytes": max(0, 1_000_000_000 - args.cache_mib * 100_000),
        "expert_materialized_bytes": 2_000_000_000,
        "expert_evictions": 3,
    }
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(json.dumps(payload), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
