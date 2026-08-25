# Native runtime

ElasticUMA's user commands wrap a Swift/Metal inference runtime. The runtime is
reconstructed from a pinned upstream commit plus one reviewable patch instead
of storing a second generated source tree in this repository.

```bash
uv run euma runtime install
uv run euma runtime status
```

Pinned inputs:

- upstream: <https://github.com/dwijenpatel/slipstream>
- commit: `01f7d5e774ca940982ea3aa012bd880b5c9d634e`
- patch: `patches/elasticuma-purgeable.patch`
- patch SHA-256:
  `9db7cbc8ce330068f292174e06834af43bf1607091a538d3dbad9f3eba4e1733`

The installer verifies the complete staged diff, rejects additional source
changes, and builds the repacker, one-shot CLI, and loopback API server under
ignored `.runtime/elasticuma/`.

## What the patch adds

- Metal-owned per-expert cache slots;
- hot non-reclaimable and cold reclaimable residency;
- relock-before-hit validation;
- exact reload after macOS discards cold contents;
- GPU-safe transitions during prefill and decode; and
- CLI/server controls for the residency policy.

## Architecture support

The pinned runtime currently implements the exact Qwen3.6-35B-A3B and Gemma 4
26B-A4B paths used by the built-in profiles. It is not a generic MoE executor.
See [the model matrix](../docs/models.md) before adding or downloading another
checkpoint.

The upstream source and patch are Apache-2.0. Preserve all upstream notices when
redistributing a reconstructed tree.
