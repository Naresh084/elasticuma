#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from elasticuma.slipstream import parse_slipstream_stderr

SLOT_BY_CACHE_MIB = {
    # Gemma 4: 1.6875 MiB/slot/layer x 30 layers.
    810: 16,
    4860: 96,
    # Qwen3.6: 1.775 MiB/slot/layer x 40 layers (runtime-declared labels).
    1136: 16,
    1704: 24,
    2272: 32,
    3408: 48,
    4544: 64,
    6816: 96,
    9088: 128,
    13632: 192,
}


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def runtime_binary() -> Path:
    configured = os.environ.get("ELASTICUMA_SLIPSTREAM_BIN")
    if configured:
        return Path(configured)
    project = Path(__file__).resolve().parents[1]
    return project / ".runtime/slipstream/.build/release/slipstream"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--prompt-file", type=Path, required=True)
    parser.add_argument("--cache-mib", type=int, choices=sorted(SLOT_BY_CACHE_MIB), required=True)
    parser.add_argument("--context", type=int, required=True)
    parser.add_argument("--max-tokens", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument(
        "--expert-cache-residency",
        choices=("fixed", "os-managed"),
        default="fixed",
    )
    parser.add_argument("--expert-cache-hot-slots", type=int, default=16)
    parser.add_argument("--result", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    binary = runtime_binary()
    if not binary.is_file():
        raise SystemExit(f"pinned slipstream binary is missing: {binary}")
    if not args.model.is_dir() or not (args.model / "verified-install.json").is_file():
        raise SystemExit(f"verified packed model is missing: {args.model}")
    prompt = args.prompt_file.read_text(encoding="utf-8")
    messages_path = args.result.parent / "messages.json"
    messages_path.write_text(
        json.dumps([{"role": "user", "content": prompt}], ensure_ascii=False),
        encoding="utf-8",
    )
    command = [
        str(binary),
        "--model",
        str(args.model),
        "--messages-file",
        str(messages_path),
        "--max-new",
        str(args.max_tokens),
        "--max-context",
        str(args.context),
        "--temperature",
        "0",
        "--top-k",
        "0",
        "--top-p",
        "1",
        "--seed",
        str(args.seed),
        "--expert-cache-slots",
        str(SLOT_BY_CACHE_MIB[args.cache_mib]),
        "--prefill-chunk",
        "auto",
        "--rdadvise",
        "off",
    ]
    if args.expert_cache_residency == "os-managed":
        if not 0 <= args.expert_cache_hot_slots <= SLOT_BY_CACHE_MIB[args.cache_mib]:
            raise SystemExit("expert cache hot slots must fit the configured cache")
        command.extend(
            [
                "--expert-cache-residency",
                args.expert_cache_residency,
                "--expert-cache-hot-slots",
                str(args.expert_cache_hot_slots),
            ]
        )
    environment = os.environ.copy()
    environment["TURBO_FIELDFARE_PHASES"] = "1"
    completed = subprocess.run(command, capture_output=True, env=environment)
    stdout = completed.stdout.decode("utf-8", errors="replace")
    stderr = completed.stderr.decode("utf-8", errors="replace")
    sys.stdout.write(stdout)
    sys.stderr.write(stderr)
    if completed.returncode != 0:
        return completed.returncode
    try:
        telemetry = parse_slipstream_stderr(stderr)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    payload = {
        "adapter": "slipstream-cli-v1",
        "runtime_binary": str(binary),
        "runtime_binary_sha256": sha256_file(binary),
        "runtime_command_sha256": sha256_text(json.dumps(command, separators=(",", ":"))),
        **telemetry,
        "text": stdout,
        "output_sha256": sha256_text(stdout),
        "expert_cache_slots": SLOT_BY_CACHE_MIB[args.cache_mib],
        "expert_cache_budget_mib": args.cache_mib,
    }
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
