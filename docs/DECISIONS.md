# Research decision log

This is an append-only record of material choices, failures, and pivots. It
exists to prevent circular retries and hindsight-driven experimental changes.

## 2026-08-24 — Scope the contribution to joint UMA control

**Decision:** Do not pursue a direct FreeToken port as the claimed novelty.
Target pressure-aware joint allocation of expert cache, inference state,
speculation, and OS headroom on Apple unified memory.

**Reason:** Heterogeneous MoE offload, explicit expert caching, SSD streaming,
bit slicing, native Metal kernels, and memory-aware speculation each have direct
prior art. Apple UMA creates a distinct shared-pool control problem, but that is
still a hypothesis until Gate 1 passes.

## 2026-08-24 — Qwen model roles

**Decision:** Use Qwen3.6-35B-A3B Q4 as the primary MoE development model. Treat
Qwen3.8-27B as a future dense control, not as capacity evidence.

**Reason:** The MoE's routed expert set lets us vary explicit expert residency.
A dense 27B model cannot validate an MoE expert-cache controller.

## 2026-08-24 — Pin slipstream as the initial executor

**Decision:** Use the external Apache-2.0 slipstream runtime at commit
`01f7d5e774ca940982ea3aa012bd880b5c9d634e` without modifying its source for the
initial characterization.

**Reason:** It already supplies native Apple-Silicon execution, a bounded routed
expert cache, exact fixed cache knobs, immutable Qwen support, and machine-readable
phase statistics. This isolates the proposed contribution to measurement and
control rather than re-claiming an executor.

## 2026-08-24 — Upstream test deviation

**Observation:** The pinned runtime's `Scripts/test.sh` ran 587 tests in 117
suites and reported five issues, all in `RepackCLITests`. Those tests look for a
debug executable named `TurboFieldfareRepack`, while the package now builds the
product as `slipstream-repack`. Kernel, loader, streaming, inference, and other
observed suites passed. Both required release products built successfully.

**Decision:** Record the packaging-test mismatch and do not patch the external
baseline checkout. Gate-1 results will pin this deviation. A future fork must
separate upstream changes from ElasticUMA contributions.

## 2026-08-24 — One-copy model storage

**Decision:** Stream the pinned source once directly into
`~/Library/Caches/elasticuma/packed/`; do not first create a Hugging Face snapshot.
Use one global download lock, an immutable canonical path, resumable partial state,
a 100 GiB free-disk reserve, and a 120 GiB store limit.

**Reason:** Keeping both source safetensors and a repacked model would consume
roughly two model copies and violate the user's storage constraint. Existing
complete snapshots are detected before transfer; deletion is never automatic.

## 2026-08-24 — Capability-gated token parity

**Decision:** Require response-text SHA-256 equality in Gate 1 but set
`require_token_id_parity=false`.

**Reason:** The pinned runtime exposes deterministic generated text and token
counts but not generated token IDs. Rejecting every row would test adapter
capability rather than inference correctness. The limitation is explicit in the
config and claim ledger; token parity remains mandatory for future capable
adapters.

## 2026-08-24 — Measure peak pressure

**Decision:** Use peak in-run compressor/swap growth and worst pressure level in
addition to end-minus-start deltas.

**Reason:** macOS may reclaim or decompress before the process exits. Endpoints
alone can erase the transient pressure event that caused a throughput cliff.

## 2026-08-24 — Gate 1 v1 stopped; safety protocol v2

**Observation:** The v1 forward warmup completed 16, 32, and 64-slot rows. The
96-slot row grew swap by 207.5 MiB within 11 seconds while free percentage
remained at least 33%; the 128 MiB live guard terminated the complete process
group. No measured v1 rows ran, no admitted artifact was produced, and 128/192
slots were never attempted.

**Decision:** Preserve v1 raw receipts and do not retry its unchanged protocol.
Create `gate1-m1max-qwen36-q4-v2` with six points from 8 to 96 slots, a higher
25% free-memory stop, bounded 384 MiB per-row swap growth, a native critical-event
stop, and three stable recovery observations before each row. The 15% throughput
gate, five repetitions, output parity, prompt, seed, and model/runtime pins do
not change.

**Reason:** The v1 event is evidence that swap begins well before the original
12% free guard, while 128 MiB is too small to observe the candidate 96-slot
configuration to completion. Removing 128/192 avoids knowingly entering a
deeper pressure regime. The new swap ceiling is explicitly data-informed and is
a safety ceiling, not the scientific effect threshold.

## 2026-08-24 — Gate 1 v2 rejected an invalid Qwen slot count

**Observation:** V2's first 8-slot warmup returned before inference with the
runtime error: `prefill routed tile depth 1 with 8 experts/tile needs 16 slots,
has 8`. Memory stayed normal, swap did not grow, and no measured row ran.

**Decision:** Preserve v2 and create v3 by replacing only 8 slots with 24. Remove
8 slots from the Qwen wrapper's accepted cache budgets. Retain every v2 safety
and scientific threshold unchanged.

**Reason:** The generic CLI advertises 8 slots, but this Qwen prefill path has a
model-specific 16-slot minimum. V3 is a compatibility correction backed by a
deterministic runtime error, not a performance-driven arm substitution.

## 2026-08-24 — Separate warmup and measured swap ceilings in v4

**Observation:** V3 completed warmups through 64 slots. During the 96-slot
warmup, swap stayed flat for roughly six seconds, then grew 476.4 MiB during
prefill; free percentage remained at least 33%, no native critical event fired,
and the 384 MiB limit terminated the process before it emitted output. The
system returned to 61% free after exit.

**Decision:** V4 keeps v3's arms and all measured-row rules, but permits at most
768 MiB swap growth during excluded warmups. Measured rows remain capped at
384 MiB; the 25% free and native-critical stops do not change. If the 96-slot
warmup exceeds 768 MiB or any measured 96-slot row exceeds 384 MiB, do not raise
the limit again; treat that configuration as infeasible under this host state.

**Reason:** The trace localizes the displacement to cache allocation/prefill,
before the first generated byte. A bounded warmup exists to absorb one-time
materialization effects. Separating its safety allowance from the paper's
measured rows is more principled than shortening generation, which cannot affect
a pre-decode event, or repeatedly raising the measured ceiling.

## 2026-08-24 — Pivot to a single-copy expert-I/O gate

**Decision:** After Gate 1 rejected the expert-cache-only controller hypothesis,
do not implement that controller. Test buffered `pread`, `F_NOCACHE`, file-backed
mmap+Metal, and MTLIO in a standalone mechanism gate before modifying the model
runtime.

**Reason:** Source audit shows the routed hot path uses concurrent buffered
`pread` into anonymous Metal slots, while its file descriptors do not request
`F_NOCACHE`. Gate 1 measured increasing compressor growth with cache capacity.
The possibility of page-cache plus slot duplication is therefore concrete but
unproven. A one-layer benchmark can falsify I/O choices cheaply and exactly.

**V1 correction:** The first I/O matrix included reusable MTLIO queue/handle
creation in timed load latency, while buffered file/slot setup was excluded.
Preserve v1, move reusable MTLIO setup outside timing in v2, and do not change
the 15% speed or 50%-memory/10%-slowdown authorization rules.

**V2 result:** Fair setup reuse left shared-buffer MTLIO 10.3% slower while
reducing peak process RSS 61.6%. This misses the alternative rule by roughly 0.3
percentage points and is not rounded into a pass.

**V3 result:** With six Latin-balanced repetitions, shared-buffer MTLIO was
21.8% slower and a private-arena MTLIO path was 2.3× slower than buffered
`pread`; neither reduced well-sampled peak RSS. Direct mmap had already shown a
roughly 24× slowdown. The I/O family is rejected.

**Cleanup:** Remove the failed I/O executable and runner from the implementation
and default native build. Retain only these decision notes and machine-local
ignored receipts for research integrity. Future failed prototypes follow the
same rule; only a passing mechanism is promoted into maintained code.

## 2026-08-24 — Reject lossless and compressed-MTLIO experts

**Screen:** Sixteen Q4 expert blocks compressed 1.61–1.65× with zlib/LZFSE/zstd,
but CPU decode reached only 0.46–2.85 GiB/s across tested codecs. Apple Metal-LZ4
compressed a full 452,984,832-byte layer to 326,861,313 bytes (1.39×).

**Direct-load result:** Across six balanced orders on 96 identical expert
blocks, raw buffered/MTLIO loads settled near 4.6–5.2 ms when warm; compressed
MTLIO took roughly 15–20 ms with identical checksums. Direct decompression was
about 3× slower than the raw path.

**Decision:** Reject lossless compression, CPU decompression, and compressed
MTLIO for this system. Do not add the prototype or compressed model artifact to
the repository. ZipMoE also occupies the broad lossless-compression claim space.

## 2026-08-24 — Purgeable Metal cache: retain the primitive, reject coarse scheduling

**Allocation prerequisite:** A five-pair, 256-token gate comparing the pinned
external slot allocation with Metal-owned per-slot buffers produced identical
output and cache outcomes in all ten measured rows. The Metal-owned allocation's
paired median slowdown was 3.59% (observed range -1.90% faster to 5.66% slower),
so it authorized purgeability work. The user's later 10% deployment budget was
not retroactively treated as proof; successor claims require fresh rows.

**Primitive result:** Calling `setPurgeableState(.empty)` on Metal-owned shared
buffers released 93–98% of touched RSS in isolated probes and returned `.empty`
when relocked. The existing `bytesNoCopy` buffers did not release their external
allocation. Exact recovery therefore requires Metal ownership, a stable slot
resource, an authoritative relock check, logical invalidation on `.empty`, and
`pread` before the resource is rebound.

**Rejected layer-arena policy:** One purgeable buffer per layer reduced a
4-GiB-pressure probe's measured model RSS from 3.38 to 1.92 GiB, but macOS
discarded almost every layer each token. Effective hit rate collapsed from
88.0% to 1.3% and throughput from 11.05 to 6.01 tok/s. Remove the layer-arena
implementation; do not optimize or publish it.

**Selective-slot v3 result:** Keeping the hottest 16 of 96 slots per layer and
making the cold 80 volatile preserved exact output across ten admitted held-out
rows. Paired median throughput was 6.66% faster, but the deterministic bootstrap
95% interval ranged from 24.62% faster to 15.97% slower, violating the frozen
10% upper bound. Median peak `phys_footprint` fell only 3.34%, and combined peak
compressor/swap growth was 238.8 MiB worse. The frozen capacity gate therefore
failed despite non-zero exact recovery in every candidate row.

**Pivot:** Retain the reload-correct per-slot primitive, but remove the failed
post-prefill-only schedule. V3 showed that the full 96-slot cache becomes
resident before the first volatility callback. The next protocol moves the same
hot/cold transition to an already-synchronized per-layer prefill boundary so
earlier layers become reclaimable before later layers materialize. It remains a
new mechanism and requires a newly named held-out gate; v3 is not reinterpreted.

**Telemetry correction:** RSS counts reclaimable pages and is not the primary
Apple memory metric for this mechanism. Record `ri_phys_footprint` directly via
`proc_pid_rusage`, while retaining RSS, compressor, swap, free percentage, and
native pressure events. Purge transitions and recovery counters must be emitted
as machine-readable integers.

**Storage cleanup:** Keep the one verified Qwen3.6 MoE and one Qwen3.8 dense
control snapshot; neither is a duplicate. Cleaned obsolete baseline debug and
primitive build products (about 923 MiB) and rebuilt only the pinned release
binary. The active fork build remains until its mechanism is either promoted or
rejected, preventing repeated recompilation and duplicate model downloads.

## 2026-08-24 — Promote layerwise purgeability after two fresh strong-baseline gates

**V5 authorization:** Moving hot/cold transitions into the synchronized prefill
layer loop fixed v3's peak-materialization flaw. On a second unseen prompt, all
ten measured fixed/selective rows were admitted. The candidate won all five
pairs (paired median gain 16.09%, bootstrap interval 6.53–40.02%), reduced peak
physical footprint 33.46%, and reduced peak compressor growth 4.96 GiB.

**Committed implementation:** Promote only the passing Metal-owned per-slot
design into runtime commit `ec84269d5ce162a0376099d39b30dd19aa99f096`, whose
upstream parent is `01f7d5e774ca940982ea3aa012bd880b5c9d634e`. Expose explicit
CLI/server `fixed|os-managed` and hot-slot controls. Move token-safe transitions
inside the runner so front ends cannot omit them. Development used a clean
sibling runtime checkout; the public release reconstructs the same committed
diff from the pinned upstream commit and the bundled patch. No model/build copy
is stored in Git.

**V6 pressure result:** Against untouched upstream fixed-16 and fixed-96
executors under a bounded 4 GiB co-tenant, all fifteen measured rows were
admitted with one output hash and both executor hashes. ElasticUMA's paired
median gains were 7.25% over fixed-16 and 13.67% over fixed-96. It retained
38.92 additional hit-rate points over fixed-16, cut fixed-96 peak footprint
31.64%, and cut peak compressor growth 5.05 GiB.

**V7 no-pressure result:** On another unseen prompt with no pressure worker,
all fifteen rows were admitted; the candidate beat both upstream baselines in
every pair. Paired median gains were 16.91% over fixed-16 and 17.59% over
fixed-96; fixed-96 peak footprint fell 31.65% and compressor growth fell
5.29 GiB. This rejects the explanation that the gain is only an artifact of the
synthetic co-tenant.

**Decision:** The result is a scoped breakthrough candidate and may enter the
paper as a single-host/Qwen result. Do not generalize to all Macs or MoEs until
second-architecture, other-chip, energy, and independent-reproduction gates
pass. Keep failed layer-arena and post-prefill-only schedules out of maintained
code.

**Gemma V8 update:** The one-copy Gemma 4 26B-A4B gate subsequently admitted all
15 measured rows. ElasticUMA won every pair: paired median gains were 45.30%
over upstream-16 and 26.01% over upstream-96; fixed-96 peak footprint fell
35.26% and compressor growth fell 4.04 GiB. Second-architecture scope is now
admitted on the same M1 Max; cross-chip and independent scope remain open.

## 2026-08-24 — Qwen3.8 dense control is not safely sustained on this host

The exact one-copy `Qwen3.8-27B-4bit` snapshot runs with MLX 0.32.1 and mlx-vlm
0.6.14 after applying the upstream-required `mx.clear_streams()` teardown.
One 128-token measured diagnostic produced 11.36 token/s at 17.96 GiB sampled
peak physical footprint (18.60 GiB MLX peak), 20% minimum free memory, and
151 MiB swap growth. A later row crossed the frozen 20% guard at 19% and was
terminated.

**Decision:** Preserve the complete rows as diagnostic capacity evidence but do
not admit or quote them as a sustained dense-vs-MoE speed comparison. Do not
download another Qwen3.8 quantization to rescue the gate. Use the already-pinned
Gemma 4 architecture for the next one-copy generalization test.
