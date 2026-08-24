# Prior-art and novelty audit

Audit date: 25 August 2026. This document uses primary papers, repositories,
and pull requests. “Closest” means closest to the proposed systems contribution,
not necessarily the fastest implementation.

## Executive novelty boundary

There is already an open FreeToken Apple-Silicon pull request, but it delegates
generation to MLX-LM or llama.cpp and supplies installation, proxy, lifecycle,
and API compatibility. It is not a port of FreeToken's CUDA expert cache or
bandwidth-adaptive execution engine. There is also a closed MLX-LM pull request
that implements real disk-backed expert fetching. Numerous independent Mac
runtimes already stream experts from SSD.

Therefore none of these are defensible ElasticUMA claims:

- “FreeToken on Mac,” “MoE larger than RAM on Mac,” or “SSD expert streaming”;
- explicit LRU expert caching or OS page-cache ownership;
- dynamic cache resizing by itself;
- native Metal inference or CPU/GPU co-execution;
- bit-sliced experts, lossless expert compression, or memory-aware speculation.

Gate 1 rejected the original cache-size controller. The admitted contribution is
narrower and materially different: **Metal-owned per-expert slots whose cold
pages become OS-reclaimable at real GPU-safe boundaries, with relock-before-hit
validation and exact positional reload after `.empty`.** The claim is scoped to
Qwen3.6 and Gemma 4 on one M1 Max; it is not a general Mac, model, or controller
claim.

## Public-interface reference

FreeToken's `main` README at commit `2a56a086537ed077a0702666158bec275d1e9486`
provides a particularly clear public path: one short CLI, one required model
argument, automatic hardware/model defaults, separate install/quick-start/model/
CLI guides, local compatible APIs, and exact contribution requirements.
ElasticUMA follows that onboarding discipline but copies no FreeToken source.
Its native data plane and Apple-UMA mechanism remain independent.

## Closest implementation work

| Work | What it already establishes | Boundary for ElasticUMA |
|---|---|---|
| [FreeToken](https://arxiv.org/abs/2608.16157) / [code](https://github.com/FlashML-org/FreeToken) | Global GPU expert LRU, prefill double buffering, calibrated CPU/GPU miss execution, semantic state caches, and idle-point elastic VRAM management on CUDA systems | Credit all heterogeneous execution and elastic-cache ideas. Apple UMA has no host-to-device PCIe split; our claim must concern shared physical pressure and joint consumers. |
| [FreeToken PR #65](https://github.com/FlashML-org/FreeToken/pull/65) | Open macOS/arm64 installation and serving layer over MLX-LM or llama.cpp; tests and API lifecycle | An existing Mac PR, but not an out-of-core expert engine. Compare control-plane scope explicitly; do not say no Mac support exists. |
| [MLX-LM PR #1588](https://github.com/ml-explore/mlx-lm/pull/1588) | Opt-in disk-backed `SwitchLinear`/`QuantizedSwitchLinear`, lazy load rules, independent resident experts, async I/O staging, bounded memory, and concrete synchronization optimizations | Closest upstream-quality expert-offload primitive. It was closed unmerged; its code and negative lessons remain prior art. |
| [MawForge](https://arxiv.org/abs/2607.09686) | Bounded expert materialization on unified-memory local systems; cache/quantization/route-locality tradeoffs | Direct Mac systems baseline. A fixed cache versus controller comparison is mandatory. |
| [slipstream](https://github.com/dwijenpatel/slipstream) | Native Metal kernels, packed storage, direct bounded expert streaming, persistent slots, Qwen/Gemma support, phase/cache telemetry | Initial executor and fixed-policy baseline, not an ElasticUMA contribution. |
| [TurboFieldfare](https://github.com/drumih/turbo-fieldfare) | Native Mac storage-backed MoE execution lineage | Cite lineage and compare compatible releases. |
| [SwiftLM](https://github.com/SharpAI/SwiftLM) / [PR #26](https://github.com/SharpAI/SwiftLM/pull/26) | Persistent expert buffers, parallel `pread`, grouped expert execution, Swift/C++ hot path, KV compression, large over-RAM demonstrations | Strong external bounded-memory baseline; its reported cache/page-cache and speculation anti-results motivate joint control but are not ours. |
| [mlx-moe-offload](https://github.com/huckiyang/mlx-moe-offload) | Exact mmap/page-cache-backed routed experts with bounded resident state | Kernel-managed/page-cache baseline; deep-offload throughput can be extremely low and must not be compared only by capacity. |
| [blackmlx](https://github.com/lBroth/blackmlx) | Exact per-layer expert slots and high-throughput moderate-offload reports | Explicit-slot baseline and evidence that hit-rate regime determines the cliff. |
| [mbolt](https://github.com/doramirdor/mbolt) | Coalesced expert layout and profile-guided experiments, including negative prediction/static-pinning results | Layout is a baseline/component, not controller novelty. |

## Papers that occupy obvious contribution space

| Topic | Direct work | Consequence |
|---|---|---|
| Heterogeneous MoE serving | FreeToken; Fiddler; HeteGen; MoE-Infinity | CPU/GPU expert execution and offload are established. |
| Apple CPU/GPU co-execution | [FusionML](https://arxiv.org/abs/2607.22785) | Treat phase-specific CPU/GPU splitting as prior art; its decode boundary constrains our design. |
| Apple NPU/ANE MoE execution | [NPUMoE](https://arxiv.org/abs/2604.18788) | ANE use is complementary, not headline novelty. |
| Native Metal LLM runtime | [BaseRT](https://arxiv.org/abs/2607.00501) | Kernel/runtime efficiency is a baseline; resident decode is often bandwidth-bound. |
| Bit-sliced expert cache | [SliceMoE](https://arxiv.org/abs/2512.12990); [ELMoE-3D](https://arxiv.org/abs/2604.14626) | Do not claim slicing or multi-precision expert tiers as new. |
| Lossless expert compression | [ZipMoE](https://arxiv.org/abs/2601.21198) | Compression may be an optional module or baseline only. |
| Memory-aware speculation | [MemSpec](https://arxiv.org/abs/2608.10362); [EcoSpec](https://arxiv.org/abs/2607.12696); MoE-Spec; AcceptMoE | Controlling speculative depth alone is occupied. Joint control must demonstrate interaction with shared UMA pressure. |
| Offload plus speculation | [SpecOffload](https://arxiv.org/abs/2505.10259) | Differentiate through Apple pressure, routed storage, exact state transitions, and joint allocation. |
| Kernel-owned expert cache | [Who Should Own the Expert Cache?](https://arxiv.org/abs/2608.12103) | Compare kernel-managed and explicit caches. Its warning that some induced pressure knees are reclaim artifacts makes non-destructive, real-host evidence essential. |
| Exact W4 expert slot cache | [ExactMoE](https://arxiv.org/abs/2608.15383) | Exact quantized expert slots and fused kernels are occupied design space. |

## Current PR answer

As of the audit date and the GitHub status check on 25 August 2026:

- FreeToken [PR #65](https://github.com/FlashML-org/FreeToken/pull/65) is open.
  Its own summary says Darwin routes to an MLX or llama.cpp backend before Torch
  is imported. The changed surface is packaging, proxying, server lifecycle,
  shell, and API tests. It does not implement FreeToken's CUDA MoE data plane.
- FreeToken [issue #9](https://github.com/FlashML-org/FreeToken/issues/9) requests
  Apple-Silicon support, and the [2026 roadmap](https://github.com/FlashML-org/FreeToken/issues/79)
  lists a native Metal engine as future work.
- MLX-LM [PR #1588](https://github.com/ml-explore/mlx-lm/pull/1588) is closed and
  unmerged. It remains the closest direct upstream expert-offload change.

These states can change. A paper submission must repeat this audit and record
commit/status timestamps rather than copying this paragraph unchanged.

## What could still invalidate the paper

The project should stop or pivot if any of the following is found:

1. a maintained Apple runtime already implements per-expert OS-purgeable Metal
   residency with safe-point transitions, relock-before-hit validation, exact
   empty-slot recovery, and an earlier public evaluation;
2. the footprint benefit disappears when measured on another operator's Mac or
   is explained entirely by an instrumentation artifact;
3. a strong existing fixed/page-cache policy matches the same throughput,
   footprint, and exact-recovery point under equal conditions;
4. purgeability changes output semantics, races a live GPU command, or permits
   an `.empty` slot to be consumed as a hit; or
5. the effect fails across Apple generations or realistic concurrent desktop
   traces, forcing the paper claim to remain a single-host mechanism report.

## Review checklist before submission

- Re-search GitHub issues, PRs, arXiv, proceedings, and artifact repositories.
- Read full papers—not abstracts—for FreeToken, MawForge, the kernel-cache paper,
  MemSpec, EcoSpec, FusionML, and the strongest Apple baselines.
- Add author, venue/status, version, evaluation hardware, supported model
  architectures, source availability, and exact claimed contributions to a
  machine-readable literature table.
- Ask at least one uninvolved systems researcher to state the novelty difference
  in one sentence. If they cannot, the paper is not ready.
- Cite inherited runtime code and upstream performance as such; never merge it
  into ElasticUMA's measured columns.
