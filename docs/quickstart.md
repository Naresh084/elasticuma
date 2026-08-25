# Quick start

## 1. Install

```bash
git clone https://github.com/Naresh084/elasticuma.git
cd elasticuma
./install.sh
```

The installer creates the Python environment and reconstructs the pinned
Swift/Metal runtime. It does not download a model.

## 2. Pick and install a model

### Native Mac app

```bash
uv run euma app open
```

Choose a verified model in **Models**, approve its storage plan, then return to
**Chat**. The app, CLI, and SDK reuse the same canonical model copy.

The Models screen also searches Hugging Face live. A result is installable only
when its complete native shape and tensor-index fingerprint are admitted. Input
badges are per model; both current built-in profiles are text-only in
ElasticUMA.

### Terminal

```bash
uv run euma models
uv run euma setup qwen36
```

`setup` checks the canonical cache, existing Hugging Face snapshots, model size,
free disk, and the disk reserve before asking for confirmation. A completed
install is reused; an interrupted pack resumes instead of starting another
model copy.

## 3. Generate from the terminal

```bash
uv run euma run qwen36 "Why can a large cache make a Mac slower?"
```

Useful options:

```bash
uv run euma run qwen36 "Write a Swift example." --max-new 512
uv run euma run qwen36 "Hello" --dry-run
```

## 4. Start the local API

```bash
uv run euma serve qwen36
```

In another terminal, use either client protocol.

OpenAI-compatible request:

```bash
curl http://127.0.0.1:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "qwen36",
    "messages": [{"role": "user", "content": "What is an MoE model?"}],
    "max_tokens": 256,
    "stream": true
  }'
```

Anthropic-compatible request:

```bash
curl http://127.0.0.1:8080/v1/messages \
  -H 'Content-Type: application/json' \
  -H 'anthropic-version: 2023-06-01' \
  -d '{
    "model": "qwen36",
    "messages": [{"role": "user", "content": "What is an MoE model?"}],
    "max_tokens": 256,
    "stream": true
  }'
```

The server is loopback-only and stops with `Ctrl-C`. ElasticUMA refuses to start
while another recognized local model server is running; it never kills another
process.

## Use a compatible packed model

If the native runtime already supports its architecture and the directory has a
valid `.gturbo` manifest and install receipt:

```bash
uv run euma serve /absolute/path/to/model.gturbo
```

Read [models.md](models.md) before treating a different checkpoint as supported.
