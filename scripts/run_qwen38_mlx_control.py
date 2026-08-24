#!/usr/bin/env python3
from __future__ import annotations

import argparse
import atexit
import hashlib
import importlib.metadata
import json
import os
import time
from pathlib import Path


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--prompt-file", type=Path, required=True)
    parser.add_argument("--max-tokens", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--result", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.model.is_dir() or not (args.model / "config.json").is_file():
        raise SystemExit(f"local MLX model snapshot is incomplete: {args.model}")
    if not list(args.model.glob("model-*-of-*.safetensors")):
        raise SystemExit(f"local MLX weight shards are missing: {args.model}")
    if args.max_tokens <= 0:
        raise SystemExit("max-tokens must be positive")

    # A local path plus offline flags makes a second model transfer impossible.
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_DATASETS_OFFLINE"] = "1"

    import mlx.core as mx
    from mlx_vlm import generate, load
    from mlx_vlm.prompt_utils import apply_chat_template
    from mlx_vlm.utils import load_config

    # MLX 0.32 requires main-thread streams to be cleared before Python module
    # teardown. mlx-vlm issue #1945 documents the otherwise successful
    # generation followed by exit 134/139 during interpreter finalization.
    atexit.register(mx.clear_streams)

    prompt = args.prompt_file.read_text(encoding="utf-8")
    load_started = time.monotonic()
    model, processor = load(str(args.model), lazy=False, strict=True)
    load_seconds = time.monotonic() - load_started
    config = load_config(args.model)
    formatted = apply_chat_template(
        processor,
        config,
        prompt,
        add_generation_prompt=True,
        num_images=0,
        num_audios=0,
    )
    generated = generate(
        model,
        processor,
        formatted,
        max_tokens=args.max_tokens,
        temperature=0.0,
        seed=args.seed,
        verbose=False,
    )
    payload = {
        "adapter": "mlx-vlm-control-v1",
        "model_path": str(args.model),
        "mlx_version": importlib.metadata.version("mlx"),
        "mlx_vlm_version": importlib.metadata.version("mlx-vlm"),
        "transformers_version": importlib.metadata.version("transformers"),
        "load_seconds": load_seconds,
        "prompt_tokens": int(generated.prompt_tokens),
        "completion_tokens": int(generated.generation_tokens),
        "prompt_tps": float(generated.prompt_tps),
        "decode_tps": float(generated.generation_tps),
        "text": generated.text,
        "output_sha256": sha256_text(generated.text),
        "finish_reason": generated.finish_reason,
        "runtime_reported_peak_memory_gib": float(generated.peak_memory),
        "seed": args.seed,
    }
    args.result.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.result.with_suffix(args.result.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(args.result)
    print(generated.text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
