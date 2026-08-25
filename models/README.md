# Model profiles

The two verified profiles ship inside the Python package. Run:

```bash
uv run euma models
```

Additional `*.json` files in this directory extend the catalog only for a
checkpoint whose architecture is already implemented by the native runtime.
Start from `example.community.json.example`, pin the repository revision and
source hash, and keep `verification` set to `community`.

A profile is metadata. It does not add a tokenizer, tensor mapping, router, or
Metal kernel. New architectures require native code and correctness tests; see
[docs/models.md](../docs/models.md).

Never place weights, tokenizers, `.gturbo` directories, credentials, or local
paths here. Models belong in the canonical cache outside Git.
