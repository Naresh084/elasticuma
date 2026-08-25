# Native runtime

ElasticUMA's user commands wrap a Swift/Metal inference runtime. The runtime is
reconstructed from a pinned upstream commit plus two reviewable patches instead
of storing a second generated source tree in this repository.

```bash
uv run euma runtime install
uv run euma runtime status
```

Pinned inputs:

- upstream: <https://github.com/dwijenpatel/slipstream>
- commit: `01f7d5e774ca940982ea3aa012bd880b5c9d634e`
- mechanism patch: `patches/elasticuma-purgeable.patch`
- mechanism SHA-256:
  `433f38c094aca85701129bdaa9b1e3397a0a7f8f45759c4af2050f2f0bdfbde9`
- product patch: `patches/elasticuma-app.patch`
- product SHA-256:
  `d02b916072148f6fe8c05ad8352a767f828e0eaea0c8ee010d16f52c1666e4de`
- complete staged patch-set SHA-256:
  `a009e905b3483f9e894cc8627a58de1353437565b22f3e13107364c7acb4739b`

The installer verifies the complete staged diff, rejects additional source
changes, and builds the repacker, one-shot CLI, loopback API server, decode
service, and native Mac app under
ignored `.runtime/elasticuma/`.

## What the patches add

The mechanism patch remains the paper's isolated runtime contribution:

- Metal-owned per-expert cache slots;
- hot non-reclaimable and cold reclaimable residency;
- relock-before-hit validation;
- exact reload after macOS discards cold contents;
- GPU-safe transitions during prefill and decode; and
- CLI/server controls for the residency policy.

The separate product patch adds the ElasticUMA Mac interface, canonical shared
model paths, app-to-runtime residency settings, cache telemetry, model setup,
local chat, and owned server controls. Keeping these patches separate prevents
product code from changing the paper's mechanism boundary.

## Architecture support

The pinned runtime currently implements the exact Qwen3.6-35B-A3B and Gemma 4
26B-A4B paths used by the built-in profiles. It is not a generic MoE executor.
See [the model matrix](../docs/models.md) before adding or downloading another
checkpoint.

The upstream source and patch are Apache-2.0. Preserve all upstream notices when
redistributing a reconstructed tree.
