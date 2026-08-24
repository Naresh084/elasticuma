# Model, memory, and expected-speed matrix

Evidence cutoff: 24 August 2026. “Measured upstream” numbers belong to the linked
project and are not ElasticUMA results. “Projected” values are planning ranges,
not claims. Local values remain blank until an admitted run exists.

## Qwen3.8-27B on the M1 Max/32 GB

[Qwen3.8-27B](https://huggingface.co/Qwen/Qwen3.8-27B) is a **dense** 27B
vision-language model, not an MoE. Its language stack has 64 layers, a 5,120-wide
hidden state, hybrid Gated DeltaNet/attention blocks, dense 17,408-wide FFNs,
MTP training, 262,144 native context, and a vision encoder. The official BF16
repository is roughly 55.6 GB. The current
[MLX 4-bit conversion](https://huggingface.co/mlx-community/Qwen3.8-27B-4bit)
is approximately 16.1 GB and resolves in this project to immutable revision
`3e6447f082e89cc7f0bc6e5441afd38dfce760ff`. Its guarded preflight reports
16,081,490,933 published bytes and no existing local snapshot. The
[Unsloth GGUF collection](https://huggingface.co/unsloth/Qwen3.8-27B-GGUF)
currently lists, among others, about 13.1 GB for Q3_K_XL, 15.4–17.6 GB for its
4-bit variants, 18.7–20.9 GB for 5-bit, 22–25.3 GB for 6-bit, 29–31.5 GB for
8-bit, and 54.7 GB for BF16.

### What fits safely

On this 32 GB Mac, installed RAM is not a model budget. A practical interactive
budget must leave roughly 5–8 GB for macOS, applications, filesystem/Metal
headroom, and transient allocations, then reserve inference state and scratch.

| Format | Checkpoint bytes | 32 GB assessment |
|---|---:|---|
| MLX 4-bit / GGUF Q4 | ~15–18 GB | Comfortable at short/moderate context if other applications are controlled; primary choice |
| GGUF Q5 | ~19–21 GB | Feasible but with less context and pressure headroom |
| GGUF Q6 | ~22–25 GB | Borderline; likely sensitive to context, vision, and co-tenants |
| GGUF Q8 | ~29–31.5 GB | Not a safe resident configuration on 32 GB |
| BF16 | ~55 GB | Does not fit; dense offload rereads nearly all weights per token and is not a useful capacity path |

The advertised context maximum is not a promise that the entire context fits
this machine. KV/recurrent state, retained reasoning, vision tokens, MTP buffers,
and application headroom still consume memory. Benchmark 4K first, then 16K,
32K, and longer contexts with pressure guards.

### Honest speed expectation

The M1 Max advertises up to 400 GB/s unified-memory bandwidth. Reading a 16.1 GB
dense Q4 weight set once per token gives an idealized bandwidth ceiling of about
24.8 token/s before kernel inefficiency, recurrent/attention work, sampling, and
contention. A **projected 12–20 token/s** decode range is reasonable for planning
but is not a measurement. MTP could exceed the one-token roof only when runtime
support and acceptance amortize verification; it can also regress.

A [community M4 Pro comparison](https://huggingface.co/Qwen/Qwen3.8-27B/discussions/80)
on the official model discussion reports about
20.3 token/s on unpredictable text and 38.4 token/s on predictable text for an
MLX/NVFP4 path with speculation, while its GGUF MTP path regressed on
unpredictable output. Those are useful bounds, not an M1 Max result: the engines,
quantization, prompt predictability, and chip differ. ElasticUMA will separately
report autoregressive and MTP modes rather than averaging them.

The project will report a number only after a pinned MLX/llama.cpp adapter runs
the exact same prompt, context, output length, and quantization repeatedly. It
will separate text-only language weights from vision-tower residency and record
whether thinking mode changes generated length.

### Why it is a control, not the breakthrough model

Every dense token uses essentially the whole language model. An expert cache
cannot avoid those reads. Qwen3.8-27B is valuable to test whether ElasticUMA
correctly chooses a resident quantization, state budget, and optional MTP mode;
it cannot support a “much larger model than RAM” or routed-expert capacity claim.

## Primary and generalization MoEs

| Model | Structure/role | Approx. artifact | Existing evidence | M1 Max/32 GB use |
|---|---|---:|---|---|
| Qwen3.6-35B-A3B Q4 | 35B total, ~3B active; primary Gate 1 | ~19.6 GB packed; 18.1 GB routed experts | Pinned slipstream reports 18.8–23.1 tok/s on an M5/24 GB at ~1.45 GB footprint; a separate cache sweep reports a long-prompt slowdown at 192 slots | Real local measurement in progress; best first model because it has a resident oracle and a wide explicit-cache sweep |
| Gemma 4 26B-A4B Q4 | 26B total, ~3.88B active; architecture generality | ~14.3 GB packed; 12.9 GB routed experts | Pinned runtime reports 5.1–6.3 tok/s on an 8 GB M2 and 31–35 tok/s on a 24 GB M5 Pro | Likely faster/warm-page-cache regime; required second architecture, downloaded only after Qwen evidence justifies it |
| Qwen3.5/3.6 122B-A10B Q4 | ~122B total, ~10B active; true over-RAM target | community builds around 70 GB | SwiftLM reports roughly 4.95 tok/s at full top-8 on a 64 GB M1 Ultra; not a controlled M1 Max result | Candidate Gate 3 model; common weights and minimum state must be audited before a 70 GB transfer |
| gpt-oss-120B MXFP4 | ~120B MoE, different routing/quantization | roughly 60+ GB class | Community Mac engines report high speed only when cache coverage is high | Strong second over-RAM family if a compatible exact executor exists |
| DeepSeek-V4-Flash quantized | 100B+ class storage-backed MoE | roughly 126+ GB community build | SwiftLM reports around 4.8 tok/s on an M5 Pro/64 GB; author report | Too large for the first 32 GB experiment; later deep-stream stress test |
| Qwen3.8-2.4T-A95B | 2.4T total, 95B active | far beyond local comfort | Newly released official MoE | Not a sensible M1 Max target: active/common work is itself enormous; headline parameter count is not useful service capacity |

## Expected gain categories

Do not collapse these into one multiplier.

1. **Versus resident MLX when a model fits:** an out-of-core runtime is expected
   to be slower. The gain is memory/headroom, not speed. The controller can only
   recover avoidable pressure loss relative to a badly sized cache.
2. **Versus a fixed bounded runtime:** Gate 2 targets at least 15% geometric-mean
   throughput gain, at least 90% of the per-cell oracle, and at most 5% regret
   versus a safe fallback. These are preregistered targets, not results.
3. **Versus naive deep offload:** layout, persistent slots, and native kernels
   can produce multiples, but those mechanisms belong to prior runtimes. We may
   inherit their executor benefit, not call it ElasticUMA's gain.
4. **Capacity gain:** serving a checkpoint at least 1.5 times installed RAM is
   the Gate-3 definition. Qwen3.6 Q4 and Qwen3.8 Q4 do not qualify on 32 GB;
   a 60–70 GB MoE does.
5. **Future Macs:** more memory changes which mode is optimal. A 64/128 GB Mac
   may prefer resident execution for today’s models; ElasticUMA is useful only
   if it can disable offload and spend the budget on context/speculation instead.

## Download policy

Each selected model is pinned and downloaded at most once into the canonical
cache after projected-size preflight. A new architecture is not downloaded merely
to fill a comparison table. Qwen3.8 dense benchmarking starts only after the
primary Qwen3.6 install and Gate-1 smoke are complete, and its MLX or GGUF copy is
chosen once—never both unless a controlled cross-format experiment is explicitly
approved and storage-accounted.
