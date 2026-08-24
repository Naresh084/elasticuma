# Quick start

This guide assumes [installation](install.md) and the native runtime build are
complete.

## 1. Choose a model

```bash
uv run elasticuma model catalog
```

The built-in admitted profiles are `qwen36` and `gemma4`. `installed` means the
exact packed model already exists in the canonical cache.

## 2. Install once

```bash
uv run elasticuma model preflight --profile qwen36
uv run elasticuma model install --profile qwen36
```

The second command is safe to rerun: it reuses a verified completed install or
resumes the same partial streaming repack. It does not create a repository-local
copy.

## 3. Generate once

Preview the exact native command:

```bash
uv run elasticuma run \
  --model qwen36 \
  --prompt "Explain why more cache is not always faster." \
  --dry-run
```

Run it:

```bash
uv run elasticuma run \
  --model qwen36 \
  --prompt "Explain why more cache is not always faster." \
  --max-new 256
```

By default, catalog profiles use 96 logical expert slots, keep 16 nonvolatile,
and offer the cold remainder to macOS with exact reload on reuse.

## 4. Launch the local API

```bash
uv run elasticuma serve --model qwen36
```

The server binds only to `127.0.0.1:8080`. It supports:

- `GET /health`
- `GET /v1/models`
- `POST /v1/chat/completions`
- `POST /v1/messages`

Inspect the served model:

```bash
curl http://127.0.0.1:8080/v1/models
```

Send a streaming OpenAI-compatible request:

```bash
curl http://127.0.0.1:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "qwen36",
    "messages": [{"role": "user", "content": "What is unified memory?"}],
    "max_tokens": 512,
    "stream": true
  }'
```

Stop the server with `Ctrl-C`. ElasticUMA refuses to launch if another known
model server or app is already running; it never kills another process.

A dependency-free Python client is also included:

```bash
python examples/openai_chat.py "What is unified memory?"
```

## 5. Tune explicitly when needed

```bash
uv run elasticuma serve \
  --model qwen36 \
  --cache-slots 64 \
  --hot-slots 16 \
  --max-context 8192
```

Use `--residency fixed` only for comparison or debugging. Larger logical caches
are not guaranteed to be faster, and larger contexts consume additional memory.

## Serve a compatible packed model directly

If the native runtime already supports its manifest, tokenizer, tensor layout,
and kernels:

```bash
uv run elasticuma serve --model /absolute/path/to/model.gturbo
```

The directory must contain `manifest.json`, `verified-install.json`, and
`model_weights.bin`. See [models.md](models.md) before presenting a new model as
supported.
