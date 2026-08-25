# CLI

`euma` and `elasticuma` are equivalent.

```text
euma <command> [options]
```

| Command | Purpose |
|---|---|
| `euma setup MODEL` | Build the runtime if needed, preflight, and safely install a supported model |
| `euma models` | Show verified/community models and whether they are installed |
| `euma run MODEL PROMPT` | Generate one response |
| `euma serve MODEL` | Start the local OpenAI/Anthropic-compatible API |
| `euma doctor` | Show privacy-safe Mac, toolchain, runtime, and cache readiness |
| `euma runtime install` | Reconstruct and build the pinned native runtime |
| `euma runtime status` | Check runtime provenance and binaries |
| `euma model ...` | Advanced catalog and model-store commands |

Every command supports `--help`.

## Setup

```bash
euma setup qwen36
euma setup mlx-community/Qwen3.6-35B-A3B-4bit
euma setup gemma4 --dry-run
euma setup gemma4 --yes
```

`--dry-run` never installs. `--yes` is intended for reviewed non-interactive
automation.

## Models

```bash
euma models
euma models --json
```

The normal view is a short human-readable table. JSON includes stable ids and
repository ids for scripts.

## One-shot generation

```bash
euma run MODEL "prompt" [options]
```

| Option | Default | Meaning |
|---|---:|---|
| `--max-new` | 256 | Maximum generated tokens |
| `--max-context` | 4096 | Context limit |
| `--cache-slots` | model default | Logical expert slots per layer |
| `--hot-slots` | model default | Slots kept non-reclaimable per layer |
| `--residency` | `os-managed` | `os-managed` or fixed comparison mode |
| `--seed` | unset | Deterministic sampling seed |
| `--dry-run` | off | Print the exact binary, model, and command without launching |

The former `--model` and `--prompt` flags remain accepted for compatibility.

## API server

```bash
euma serve MODEL [options]
```

| Option | Default | Meaning |
|---|---:|---|
| `--port` | 8080 | Loopback port |
| `--model-id` | profile/manifest id | Model id returned by the API |
| `--max-context` | 16384 | Context limit |
| `--queue-limit` | 4 | Maximum queued requests |
| `--cache-slots` | model default | Logical expert slots per layer |
| `--hot-slots` | model default | Slots kept non-reclaimable per layer |
| `--residency` | `os-managed` | OS-managed or fixed residency |
| `--dry-run` | off | Print the launch plan without starting the server |

The server always binds to `127.0.0.1`.

## Advanced model-store commands

```bash
euma model catalog
euma model preflight qwen36
euma model install qwen36
euma model list
```

Use the top-level `setup` and `models` commands unless you need separate steps or
machine-readable receipts.
