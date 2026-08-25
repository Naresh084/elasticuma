# ElasticUMA

**Run large routed-expert models from SSD on Apple Silicon while keeping more
unified memory available to the rest of your Mac.**

[Paper](paper/ElasticUMA-paper.pdf) ·
[Quick start](docs/quickstart.md) ·
[Supported models](docs/models.md) ·
[CLI](docs/cli.md)

## About

ElasticUMA is a local Mixture-of-Experts (MoE) inference runtime for Apple
Silicon. It is designed for models whose complete expert pool is too expensive
to keep as permanently resident cache memory.

The packed model stays on SSD. The runtime reads the experts selected for the
current tokens, keeps frequently reused experts hot, and lets macOS reclaim cold
expert-cache pages when the machine needs memory. If a cold page was reclaimed,
ElasticUMA reloads the exact expert before the GPU uses it.

The result is a larger useful expert cache without requiring every cached expert
to remain physically present in unified memory.

## What you get

- **More practical large-model serving.** The complete routed-expert pool can
  remain storage-backed instead of becoming one permanent memory allocation.
- **More cache reuse for the memory spent.** ElasticUMA keeps the identity and
  reuse history of a large logical cache while cold physical pages remain
  reclaimable.
- **Lower pressure on the rest of the Mac.** Applications, graphics, the file
  cache, compression, and model inference share the same unified-memory pool.
- **No full-model restart after reclamation.** A discarded expert becomes a
  normal cache miss and is reloaded into the existing slot.
- **Exact expert bytes.** Reclamation changes residency and latency, not model
  weights or routing semantics.
- **A simple local interface.** Generate from the terminal or use the loopback
  OpenAI- and Anthropic-compatible API.
- **One model copy.** Downloads and packing use one canonical cache with locks,
  duplicate-snapshot detection, resumable work, and a configurable disk reserve.

## How this helps with bigger models

An MoE model has three different sizes:

1. **Total capacity** — all experts stored in the checkpoint.
2. **Active work** — the small subset of experts selected for one token.
3. **Resident cache** — experts retained to avoid reading them again.

For example, Qwen3.6-35B-A3B has about 35B total parameters but activates about
3B per token. ElasticUMA keeps the full routed-expert pool in the packed model,
executes only the selected experts, and makes the cold portion of the execution
cache reclaimable.

This separates model capacity from permanently pinned expert-cache memory. It
does not remove the memory needed by shared/dense weights, context, temporary
buffers, or the active experts, and each new model architecture still needs a
correct native backend.

![ElasticUMA storage-backed expert flow and OS-reclaimable cache](assets/elasticuma-architecture.png)

## End result achieved

Validated on one M1 Max with 32 GiB unified memory:

| Model and test | Faster than small fixed cache | Faster than large fixed cache | Lower memory use than large fixed cache |
|---|---:|---:|---:|
| Qwen3.6-35B-A3B Q4, 4 GiB co-tenant | 7.25% | 13.67% | 31.64% |
| Qwen3.6-35B-A3B Q4, normal desktop state | 16.91% | 17.59% | 31.65% |
| Gemma 4 26B-A4B Q4, normal desktop state | 45.30% | 26.01% | 35.26% |

Across 45 measured runs, ElasticUMA:

- completed all 45 planned measured runs without a timeout, critical memory
  pressure, or swap growth;
- produced the same response within each controlled comparison;
- exercised real macOS reclamation and exact expert reloads;
- used roughly one-third less physical memory than the large fixed cache; and
- decoded faster than both fixed-cache baselines in the reported medians.

For the tested models, the user gets large-cache locality, lower physical memory
pressure, and better end-to-end decode throughput at the same time. The
[paper](paper/ElasticUMA-paper.pdf) contains intervals, the full methodology,
negative results, and claim limits.

## Getting started

Requirements: Apple Silicon, macOS 26+, Xcode 26 / Swift 6.2+, Python 3.11+,
Git, and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/Naresh084/elasticuma.git
cd elasticuma
./install.sh
```

Choose and install a supported model:

```bash
uv run euma models
uv run euma setup qwen36
```

Generate once:

```bash
uv run euma run qwen36 "Explain unified memory in simple language."
```

Or start the local API:

```bash
uv run euma serve qwen36
```

The API listens only on `127.0.0.1:8080`. See the
[quick start](docs/quickstart.md) for an OpenAI-compatible request example.

## Supported models

| ID | Model | Current status |
|---|---|---|
| `qwen36` | Qwen3.6-35B-A3B Q4 | Verified on M1 Max / 32 GiB |
| `gemma4` | Gemma 4 26B-A4B Q4 | Verified on M1 Max / 32 GiB |

A completed, verified `.gturbo` model can also be passed directly when its
architecture is already implemented:

```bash
uv run euma serve /path/to/model.gturbo
```

The [model matrix](docs/models.md) lists the native architecture boundary and
the current status of recent Qwen, DeepSeek, GLM, Kimi, MiniMax, Mistral,
Gemma, gpt-oss, and Mixtral models.

## Documentation

- [Install](docs/install.md)
- [Quick start](docs/quickstart.md)
- [Models and architecture matrix](docs/models.md)
- [CLI reference](docs/cli.md)
- [Native runtime](runtime/README.md)
- [Research paper](paper/ElasticUMA-paper.pdf)

## Current scope

ElasticUMA is an early research runtime. Current evidence covers one M1 Max,
two MoE architectures, batch-one text generation, and controlled short-context
workloads. It does not yet establish results across all Apple generations,
arbitrary MoE checkpoints, long-context concurrency, multimodal input, or
independent operators.

## Citation

```bibtex
@article{prajapati2026elasticuma,
  title  = {ElasticUMA: Reload-Correct OS-Managed Expert Caching for Apple Silicon},
  author = {Prajapati, Naresh},
  year   = {2026},
  note   = {Author preprint}
}
```

## License

Apache-2.0. Model checkpoints retain their own licenses and terms. See
[NOTICE](NOTICE) for upstream attribution.
