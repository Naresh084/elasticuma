# ElasticUMA

**Run routed-expert language models on Apple Silicon with a large logical cache
whose cold pages macOS can reclaim safely.**

[Paper (PDF)](paper/ElasticUMA-paper.pdf) ·
[Paper (Word)](paper/ElasticUMA-paper.docx) ·
[Quick start](docs/quickstart.md) ·
[Supported models](docs/models.md) ·
[CLI](docs/cli.md) ·
[Publish on GitHub](docs/publishing.md)

![ElasticUMA OS-managed expert residency with exact recovery](paper/figures/elasticuma-architecture.png)

ElasticUMA is an Apple-Silicon inference runtime and reproducible research
artifact for Mixture-of-Experts (MoE) models. It keeps frequently used expert
slots resident, marks cold Metal buffers purgeable at GPU-safe boundaries, and
validates every potential cache hit before reuse. If macOS reclaimed a cold
slot, ElasticUMA converts it to a normal miss and reloads the exact expert bytes
before the GPU can bind them.

The result is physical elasticity inside Apple unified memory: one logical
96-slot cache can preserve most large-cache locality without insisting that all
cold pages remain resident.

## Highlights

- **Native Apple runtime.** Swift and Metal execution with no Python in the
  per-token hot path.
- **Reload-correct OS-managed residency.** Cold expert pages are reclaimable;
  `.empty` is never treated as a hit.
- **Simple public interface.** `elasticuma run` for one-shot generation and
  `elasticuma serve` for loopback OpenAI- and Anthropic-compatible APIs.
- **One canonical model store.** Pinned revisions, one download lock, resumable
  streaming repack, duplicate-snapshot detection, and a 100 GiB default disk
  reserve.
- **Extensible model catalog.** Add a versioned JSON profile for another model
  already supported by the native `.gturbo` runtime; direct verified `.gturbo`
  paths need no Python catalog entry.
- **Evidence included.** The paper, figures, exact runtime patch, negative
  results, and a redacted 75-row core evidence bundle are tracked in Git.

## Measured scope

These are admitted measurements on one M1 Max with 32 GiB RAM, not an all-Mac
performance promise.

| Model and protocol | Gain vs fixed-16 | Gain vs fixed-96 | Fixed-96 footprint reduction |
|---|---:|---:|---:|
| Qwen3.6, 4 GiB co-tenant | +7.25% | +13.67% | 31.64% |
| Qwen3.6, no synthetic pressure | +16.91% | +17.59% | 31.65% |
| Gemma 4, no synthetic pressure | +45.30% | +26.01% | 35.26% |

All 45 positive measured rows were admitted with identical output within each
protocol and real empty-slot recovery. See [results](docs/RESULTS.md) for
intervals, exact units, hashes, and limitations. Cross-generation, energy,
long-context concurrency, and independent reproduction remain open.

## Requirements

- Apple-Silicon Mac (`arm64`)
- macOS 26 or newer
- Xcode 26 / Swift 6.2 or newer
- Python 3.11+ and [uv](https://docs.astral.sh/uv/)
- 32 GiB RAM for the two admitted profiles
- Enough model storage while preserving the configured disk reserve

No model weights or compiled runtime binaries are stored in this repository.

## Getting started

```bash
git clone https://github.com/Naresh084/elasticuma.git
cd elasticuma
uv sync --extra dev

# Clone pinned upstream source, verify and apply the bundled patch, then build.
uv run elasticuma runtime install

# Show supported profiles and whether their canonical model is already present.
uv run elasticuma model catalog

# Safety-check one transfer. This reuses an existing matching snapshot.
uv run elasticuma model preflight --profile qwen36

# Run only when preflight says allowed=true.
uv run elasticuma model install --profile qwen36

# One-shot generation with the admitted OS-managed defaults.
uv run elasticuma run --model qwen36 --prompt "Explain unified memory in one paragraph."
```

Start the local API server:

```bash
uv run elasticuma serve --model qwen36
```

Then send an OpenAI-compatible request:

```bash
curl http://127.0.0.1:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "qwen36",
    "messages": [{"role": "user", "content": "What is an MoE model?"}],
    "max_tokens": 512,
    "stream": true
  }'
```

The server is intentionally loopback-only. See the complete
[installation](docs/install.md) and [quick-start](docs/quickstart.md) guides.

## Model compatibility

Built-in, evidence-admitted profiles:

- `qwen36` — Qwen3.6-35B-A3B Q4
- `gemma4` — Gemma 4 26B-A4B Q4

ElasticUMA can also serve any completed, verified `.gturbo` directory that the
pinned native runtime can parse:

```bash
uv run elasticuma serve --model /path/to/model.gturbo
```

This is deliberately narrower than “any Hugging Face model.” A new checkpoint
of an existing supported architecture may need only a catalog profile. A new
architecture needs tokenizer, manifest/repacker, routing, tensor-layout, and
kernel support in the native runtime plus model-specific tests. The contribution
path is documented in [supported models](docs/models.md).

## Runtime provenance

The public bootstrap reconstructs the implementation instead of relying on a
private fork:

1. clone `dwijenpatel/slipstream` at
   `01f7d5e774ca940982ea3aa012bd880b5c9d634e`;
2. verify `runtime/patches/elasticuma-purgeable.patch` at SHA-256
   `dc0418cb83988d1679796af1d707dbdb03db8473fcff9c45e6ec52daee8dc850`;
3. reconstruct measured code commit `ec84269d5ce162a0376099d39b30dd19aa99f096`
   plus documentation-only public corrections in the patch;
4. apply the patch to the Git index;
5. reject any extra source change; and
6. build the repacker, CLI, and API server in release mode.

See [runtime details](runtime/README.md) and
[mechanism documentation](runtime/docs/ELASTICUMA_PURGEABLE_CACHE.md).

## Repository layout

```text
src/elasticuma/       public CLI, catalog, safety, telemetry, experiments
runtime/              exact upstream patch and mechanism documentation
models/               community profile schema and example
examples/             dependency-free local API client
docs/                 install, quick start, CLI, model support, research record
paper/                PDF, Word, Markdown, and figures
artifacts/releases/   redacted reproducibility bundle (no weights)
configs/              immutable experiment protocols
tests/                fast contract and safety tests
```

## Relationship to FreeToken

[FreeToken](https://github.com/FlashML-org/FreeToken) is a major reference for
edge-native MoE serving and for clear product onboarding. ElasticUMA adopts the
same user-facing discipline—short commands, automatic defaults, explicit model
support, local compatible APIs, and reproducible evaluation—but not its code or
resource model. FreeToken targets heterogeneous CPU/CUDA/PCIe systems;
ElasticUMA's contribution is reload-correct, OS-managed expert residency inside
one Apple unified-memory pool. See [prior art](docs/PRIOR_ART.md).

## Citation

```bibtex
@article{prajapati2026elasticuma,
  title   = {ElasticUMA: Reload-Correct OS-Managed Expert Caching for Apple Silicon},
  author  = {Prajapati, Naresh},
  year    = {2026},
  note    = {Author preprint}
}
```

## Contributing and license

Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a model-support or
performance change. Every performance claim needs a pinned A/B protocol and raw
receipts; AI-assisted work remains the human contributor's responsibility.

ElasticUMA is Apache-2.0. The bundled patch modifies Apache-2.0 upstream source;
model checkpoints retain their own licenses. See [NOTICE](NOTICE) and
[third-party components](docs/THIRD_PARTY.md).
