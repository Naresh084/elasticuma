# ElasticUMA

**Run larger Mixture-of-Experts models on Apple Silicon without forcing every
cached expert to stay in memory.**

[Paper](paper/ElasticUMA-paper.pdf) ·
[Quick start](docs/quickstart.md) ·
[Models](docs/models.md) ·
[CLI](docs/cli.md)

![How ElasticUMA lets macOS reclaim cold expert pages](assets/elasticuma-architecture.png)

## What problem does it solve?

An MoE model may contain hundreds of experts while using only a few for each
token. A small cache repeatedly reads experts from storage. A large fixed cache
avoids those reads, but on a Mac it also competes with applications, the file
cache, graphics, compression, and swap because the CPU and GPU share one memory
pool.

ElasticUMA keeps the useful identity and reuse history of a large expert cache,
but lets macOS reclaim cold cache pages when the machine needs memory. Before a
cold expert is used again, ElasticUMA checks whether its bytes survived. If not,
it reloads the exact expert before the GPU can see it.

In plain language: **keep the large cache map, but stop treating every cold page
as untouchable RAM.**

## What did it achieve?

These are validated measurements from one M1 Max with 32 GiB unified memory.
They are not promises for every Mac or model.

| Model and test | Gain vs small fixed cache | Gain vs large fixed cache | Lower memory use than large fixed cache |
|---|---:|---:|---:|
| Qwen3.6-35B-A3B Q4, 4 GiB co-tenant | 7.25% | 13.67% | 31.64% |
| Qwen3.6-35B-A3B Q4, normal desktop state | 16.91% | 17.59% | 31.65% |
| Gemma 4 26B-A4B Q4, normal desktop state | 45.30% | 26.01% | 35.26% |

All 45 measured runs passed the safety checks, produced the same response within
each test, and exercised real expert reloads. The paper contains the full method,
intervals, negative results, and limitations.

## Get started

Requirements: an Apple-Silicon Mac, macOS 26+, Xcode 26 / Swift 6.2+, Python
3.11+, Git, and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/Naresh084/elasticuma.git
cd elasticuma
./install.sh
```

See the short model list:

```bash
uv run euma models
```

Install one supported model. This performs disk and duplicate-download checks
before asking for confirmation:

```bash
uv run euma setup qwen36
```

Generate once:

```bash
uv run euma run qwen36 "Explain unified memory in simple language."
```

Or start the local OpenAI- and Anthropic-compatible API:

```bash
uv run euma serve qwen36
```

The server listens only on `127.0.0.1:8080`. See the
[quick start](docs/quickstart.md) for a request example.

## Which models work?

| ID | Model | Status |
|---|---|---|
| `qwen36` | Qwen3.6-35B-A3B Q4 | Verified on M1 Max / 32 GiB |
| `gemma4` | Gemma 4 26B-A4B Q4 | Verified on M1 Max / 32 GiB |

You can also pass a completed, verified `.gturbo` directory directly:

```bash
uv run euma serve /path/to/model.gturbo
```

### Why not claim every MoE model?

“MoE” describes a routing idea, not one universal checkpoint format. Model
families differ in tokenizer, tensor names, expert layout, quantization, shared
experts, routing math, attention state, and GPU kernels. Loading an unknown
layout can produce wrong output, not merely slower output.

FreeToken handles this the same responsible way: it publishes known-good models
whose architectures have matching kernels, rather than claiming arbitrary MoE
compatibility. ElasticUMA currently has two native architecture paths. Adding a
checkpoint of an existing path can be mostly metadata; adding a new architecture
requires native implementation and correctness tests.

The [model support page](docs/models.md) lists the architecture boundary and
current popular models from Qwen, DeepSeek, GLM, Kimi, MiniMax, Mistral, and
gpt-oss with an honest supported/not-supported status.

## How it works

1. Selected experts are read from one canonical model copy outside the
   repository.
2. Frequently reused expert slots remain resident; cold Metal-owned slots become
   reclaimable at GPU-safe boundaries.
3. Every possible reuse is validated. Reclaimed content becomes an ordinary
   cache miss and is reloaded exactly.

The inference path is Swift and Metal. Python provides the small installer,
model registry, safety checks, and user-facing commands.

## Storage safety

ElasticUMA uses one canonical cache under
`~/Library/Caches/elasticuma/`. It locks downloads, reuses a matching existing
Hugging Face snapshot, supports resumable packing, and refuses a transfer that
would violate the configured disk reserve. It does not store model weights in
this repository.

## Documentation

- [Install](docs/install.md)
- [Quick start](docs/quickstart.md)
- [Supported models and architecture matrix](docs/models.md)
- [CLI reference](docs/cli.md)
- [Native runtime and exact patch](runtime/README.md)
- [Research paper](paper/ElasticUMA-paper.pdf)

## Relationship to FreeToken

[FreeToken](https://github.com/FlashML-org/FreeToken) is the main inspiration
for treating local inference as a whole-system problem and for keeping the
public interface simple. FreeToken targets heterogeneous CPU, CUDA GPU, host
memory, and PCIe resources. ElasticUMA studies a different mechanism for Apple
unified memory: reload-correct OS reclamation of cold Metal expert pages. No
FreeToken code is copied here.

## Status and limits

ElasticUMA is an early research runtime, not a universal model launcher. Current
evidence covers one M1 Max, two MoE architectures, batch-one text generation,
and short controlled workloads. Cross-generation results, energy, long-context
concurrency, multimodal input, and independent reproduction remain open.

## Citation and license

```bibtex
@article{prajapati2026elasticuma,
  title  = {ElasticUMA: Reload-Correct OS-Managed Expert Caching for Apple Silicon},
  author = {Prajapati, Naresh},
  year   = {2026},
  note   = {Author preprint}
}
```

ElasticUMA is Apache-2.0. Model checkpoints keep their own licenses and terms.
See [NOTICE](NOTICE) for upstream attribution.
