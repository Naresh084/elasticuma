# CLI reference

```text
elasticuma <command> [options]
```

`euma` is an equivalent short command. Every command supports `--help`.

| Command | Purpose |
|---|---|
| `elasticuma doctor` | Privacy-safe host, toolchain, runtime, and model readiness |
| `elasticuma runtime install` | Clone pinned upstream, verify/apply patch, build release runtime |
| `elasticuma runtime status` | Inspect patch and native binary readiness |
| `elasticuma model catalog` | List built-in/custom profiles and installation state |
| `elasticuma model preflight` | Check runtime, duplicate snapshots, disk reserve, and store limits |
| `elasticuma model install` | Resumably repack one pinned profile into the canonical store |
| `elasticuma model list` | Show registered local model receipts |
| `elasticuma run` | One-shot native generation |
| `elasticuma serve` | Loopback OpenAI/Anthropic-compatible API |
| `elasticuma experiment ...` | Reproduce evidence-gated research protocols |

## Runtime

```bash
elasticuma runtime install
elasticuma runtime status
```

Environment overrides for development:

- `ELASTICUMA_RUNTIME_ROOT` — runtime checkout/build location
- `ELASTICUMA_RUNTIME_SOURCE` — upstream Git URL or local clean source

The public patch and upstream commit remain fixed regardless of the source URL.

## Model catalog

```bash
elasticuma model catalog [--catalog /path/to/catalog.json]
elasticuma model preflight --profile qwen36 [--catalog FILE]
elasticuma model install --profile qwen36 [--catalog FILE]
elasticuma model list
```

Project-local `models/*.json` files load automatically. `--catalog` adds an
explicit file and may be repeated.

Advanced raw Hugging Face snapshot commands are retained for research adapters:

```bash
elasticuma model hf-preflight --repo OWNER/NAME --revision COMMIT
elasticuma model hf-fetch --repo OWNER/NAME --revision COMMIT
```

They do not imply that the native runtime supports the downloaded architecture.

## One-shot generation

```bash
elasticuma run --model <profile-or-gturbo-path> --prompt <text> [options]
```

| Flag | Default | Meaning |
|---|---:|---|
| `--max-new` | 256 | Generated-token limit |
| `--max-context` | 4096 | Context limit |
| `--cache-slots` | profile or 96 | Logical routed-expert slots/layer |
| `--hot-slots` | profile or 16 | Nonvolatile slots/layer |
| `--residency` | `os-managed` | `os-managed` or `fixed` |
| `--seed` | off | Deterministic sampling seed |
| `--catalog` | project catalog | Additional profile document |
| `--dry-run` | off | Print exact binary hash and command without launching |

## API server

```bash
elasticuma serve --model <profile-or-gturbo-path> [options]
```

| Flag | Default | Meaning |
|---|---:|---|
| `--port` | 8080 | Loopback port |
| `--model-id` | profile/manifest id | API model identifier |
| `--max-context` | 16384 | 4096, 8192, 16384, 32768, or 65536 |
| `--queue-limit` | 4 | Maximum queued requests |
| `--cache-slots` | profile or 96 | Logical expert slots/layer |
| `--hot-slots` | profile or 16 | Nonvolatile slots/layer |
| `--residency` | `os-managed` | `os-managed` or `fixed` |
| `--catalog` | project catalog | Additional profile document |
| `--dry-run` | off | Print launch plan without starting a process |

The native server always binds `127.0.0.1`; the wrapper exposes no host override.

## Research commands

The `experiment`, `pressure`, and legacy named model commands exist to reproduce
the paper. They are intentionally more verbose and fail closed on incomplete
telemetry. See [REPRODUCIBILITY.md](REPRODUCIBILITY.md).
