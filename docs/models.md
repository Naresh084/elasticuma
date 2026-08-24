# Supported models and extension contract

ElasticUMA separates three claims that are often confused:

1. **Catalogued** — a pinned JSON profile exists.
2. **Runtime-compatible** — the native runtime can parse and execute the packed
   model correctly.
3. **Admitted** — a complete frozen experiment passed the evidence gate.

A catalog entry alone does not make a new architecture supported.

## Built-in profiles

| Profile | Checkpoint | Architecture | Experts | Default logical/hot slots | Evidence |
|---|---|---|---:|---:|---|
| `qwen36` | `mlx-community/Qwen3.6-35B-A3B-4bit` | Qwen3.6 MoE | 256 total / 8 routed | 96 / 16 | V6 and V7 admitted on M1 Max |
| `gemma4` | `mlx-community/gemma-4-26b-a4b-it-4bit` | Gemma 4 MoE | 128 total / 8 routed | 96 / 16 | V8 admitted on M1 Max |

Both profiles pin an immutable 40-character Hugging Face revision and the
source-index SHA-256 expected in the packed manifest.

## Direct `.gturbo` compatibility

`elasticuma run` and `elasticuma serve` accept a verified `.gturbo` directory
without a Python profile. That is useful for a future or community model after
native compatibility is implemented and tested.

Required files:

```text
model.gturbo/
  manifest.json
  verified-install.json
  model_weights.bin
  ... immutable layer/tokenizer files ...
```

The native runtime remains authoritative for architecture, tokenizer, tensor,
and kernel compatibility.

## Add a checkpoint of a supported architecture

Create `models/<name>.json` from
[`models/example.community.json.example`](../models/example.community.json.example).
The loader fails closed on unknown fields, mutable revisions, malformed hashes,
unsafe identifiers, duplicate aliases, and impossible expert/cache dimensions.

Then inspect it without downloading:

```bash
uv run elasticuma model catalog
uv run elasticuma model preflight --profile <name>
```

A profile includes:

- stable id and aliases;
- exact Hub repo and immutable revision;
- source-index SHA-256;
- packed manifest model id;
- native repacker selector;
- architecture, layer, expert, and routing metadata;
- conservative default logical/hot slots; and
- verification state (`community` or `admitted`).

Community profiles must remain `community` until a new immutable experiment
passes and the claim ledger is updated.

## Add a new architecture

A new JSON file is insufficient. At minimum, implement and test:

1. source checkpoint discovery and license review;
2. tokenizer/chat-template support;
3. a versioned packed manifest and streaming repacker mapping;
4. tensor layout, quantization decoding, routing, shared experts, and recurrent
   or attention state;
5. Metal kernels and numerical fixtures;
6. exact cache identity and positional reload semantics;
7. prefill-layer and decode-token GPU-safe residency boundaries;
8. CLI/server model-id and request validation;
9. deterministic output parity against fixed residency; and
10. a balanced held-out performance/footprint protocol.

Do not reuse Qwen or Gemma constants for a superficially similar model. Model
support is a correctness boundary, not a marketing list.

## Model licenses and storage

Model weights are never part of this repository or evidence archive. Each model
retains its own license, acceptable-use terms, and access controls. ElasticUMA
does not execute remote model code.
