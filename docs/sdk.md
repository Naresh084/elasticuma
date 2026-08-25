# Python SDK

The public SDK exposes the same safe workflows as the CLI without requiring an
application to shell out or duplicate ElasticUMA's model cache.

```python
from elasticuma import ElasticUMA

client = ElasticUMA()

for model in client.models():
    print(model.id, model.support, model.input_modalities, model.installed)

plan = client.plan_setup("qwen36")
print(plan.as_dict())
```

`plan_setup` does not build or download anything. A new model transfer always
requires explicit consent:

```python
ready = client.setup("qwen36", allow_download=True)
print(ready.model_path)
```

Generate without replacing the Python process:

```python
result = client.generate("qwen36", "Explain unified memory simply.")
print(result.text)
```

`generate` captures the final answer separately from diagnostics and raises a
structured `GenerationError` when the native process fails. Qwen chat prompts
use the non-thinking template by default, so private reasoning tags are not
mixed into application output.

Manage a loopback server owned by the Python process:

```python
with client.start_server("qwen36") as server:
    print(server.endpoint)
```

The managed server accepts both OpenAI Chat Completions at
`/v1/chat/completions` and Anthropic Messages at `/v1/messages`. Leaving the
context manager stops the child process cleanly.

Build the native Mac app from Python:

```python
app = client.build_app()
print(app.path)
```

The main return types are immutable dataclasses with `as_dict()` helpers where
machine-readable output is useful. Exceptions inherit from `ElasticUMAError`;
`DownloadConfirmationRequired`, `SetupRefusedError`, `GenerationError`, and
`ServerStartError` preserve the structured plan or result that caused them.

## Safety and reuse guarantees

- Model discovery reports exact support level, architecture, input modalities,
  and verified local-install state.
- Setup performs a read-only plan first and never downloads unless
  `allow_download=True` is explicit.
- Completed models are reused from one canonical cache; interrupted packing is
  resumable and protected by a per-model lock.
- The SDK, CLI, and Mac app resolve the same pinned runtime and model paths.
- The managed API binds only to `127.0.0.1`.

See the runnable [SDK example](../examples/python_sdk.py).
