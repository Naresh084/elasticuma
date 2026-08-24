# Experimental methodology

This protocol is preregistered before the first Qwen Gate-1 measurement. Any
change after data collection receives a dated entry in `DECISIONS.md` and a new
experiment name; old raw data is retained.

## Research question

On Apple Silicon, routed-expert pages, explicit expert slots, non-expert model
weights, inference state, Metal allocations, the filesystem cache, applications,
and macOS share one physical memory pool. Does a larger expert cache sometimes
improve its local hit metric but reduce end-to-end throughput after the host
enters reclaim, compression, or swap pressure? If so, can a controller identify
and avoid that region from signals available online?

## Gate 1: fixed-policy characterization

The primary host is an Apple M1 Max with 24 GPU cores and 32 GB unified memory.
The immutable primary model is
`mlx-community/Qwen3.6-35B-A3B-4bit@38740b847e4cb78f352aba30aa41c76e08e6eb46`.
The runtime is
`dwijenpatel/slipstream@01f7d5e774ca940982ea3aa012bd880b5c9d634e`.

The current v4 fixed sweep uses 16, 24, 32, 48, 64, and 96 expert slots. The
runtime's declared allocation model maps these to 1,136, 1,704, 2,272, 3,408,
4,544, and 6,816 MiB. Every arm uses the same prompt, 4,096-token context limit, 256-token
maximum deterministic completion, greedy decoding, seed 104729, automatic
prefill chunking, disabled read-ahead advice, and no synthetic pressure.

V1 originally extended to 128 and 192 slots with a 12% free and 128 MiB swap
ceiling. It stopped during the 96-slot warmup after 207.5 MiB of swap growth.
V2 is explicitly post-pilot: it removes the knowingly deeper 128/192 regimes,
adds lower characterization points, requires three normal samples
at or above 40% free before each row, stops below 25% free, and permits at most
384 MiB per-row swap growth. The scientific 15% threshold is unchanged.
V2's first 8-slot arm then failed before inference because Qwen's routed prefill
needs 16 slots. V3 replaces only that invalid point with 24 slots; no scientific
or measured-row threshold changes. V3 then showed that 96-slot prefill can cause
a one-time 476.4 MiB OS displacement during warmup. V4 allows warmups up to
768 MiB swap growth while every measured row retains 384 MiB; the 25% free and
native-critical stops remain unchanged.

Order is one forward warmup sweep followed by five measured sweeps that alternate
forward and reverse order. This balances thermal/time drift without claiming
full randomization. The six warmups are never admitted. One process lock prevents
overlapping model workers.

The primary sweep requires AC power, observable low-power mode off, and no
thermal/performance warning before, between, and after rows. Power snapshots are
part of each receipt. A battery run may be retained as diagnostic evidence but
cannot enter the primary admitted dataset.

## Primary endpoint and pass rule

Decode tokens per second is the primary performance endpoint. Expert hit rate
is a mechanism metric. A candidate recoverable pressure gap requires a pair of
arms at the same co-tenant pressure where the larger cache:

1. has a strictly higher median expert hit rate;
2. has at least 15% lower median decode throughput; and
3. has independent pressure evidence: at least a two-point reduction in the
   median minimum free percentage, at least 256 MiB additional peak compressor
   growth, positive additional peak swap growth, or a worse macOS pressure
   level.

The 15% threshold was chosen before measurement to avoid building a controller
around ordinary noise. It is an engineering gate, not a confidence interval.
The pair must have all five planned paired repetitions, the same slowdown
direction in at least four, and a paired median gap of at least 15%. The report
includes a deterministic percentile-bootstrap interval for the paired median.
This is an engineering gate rather than a null-hypothesis test; all pairwise
comparisons are retained to make the exploratory multiplicity visible.

## Successor mechanism gates

Gate 1's failure forbids lowering its 15% threshold but does not forbid a
materially different mechanism. Each successor receives a new experiment name,
unseen prompt, fixed implementation/thresholds, and immutable raw directory.
Failed I/O, compression, coarse-arena, and post-prefill-only designs are retained
as negative evidence and removed from maintained runtime code.

The promoted mechanism uses 96 logical expert slots per layer, keeps the hottest
16 nonvolatile, and makes cold Metal-owned slots purgeable after each synchronized
prefill layer and decode step. A potential hit is relocked; `.empty` invalidates
the mapping and forces exact `pread` before GPU reuse.

V6 compares the committed mechanism with untouched upstream fixed-16 and
fixed-96 under one bounded 4,096 MiB co-tenant. V7 repeats all three arms without
the pressure worker. Both use one excluded warmup and five balanced measured
triples, fresh prompts, 256-token greedy completions, AC power, and executor
binary hashes. Frozen gates require complete admission/output parity, paired
median slowdown no greater than 10% with bootstrap upper bound no greater than
10%, and a material footprint/pressure benefit relative to fixed-96. The 10%
rule is a preregistered engineering threshold for these experiments, not a
universal definition of product value.

## Telemetry and receipts

Each raw run has a unique directory and includes:

- exact command hash, prompt hash, model path and immutable revisions;
- privacy-safe hardware and OS description;
- start/end memory snapshots and 0.5-second samples;
- process-tree RSS and `proc_pid_rusage().ri_phys_footprint` samples;
- return code, timeout state, and all guard failures;
- runtime-reported token counts, prefill/decode time, cache hits/misses, and
  optional MTP statistics;
- deterministic response SHA-256;
- stdout, stderr, runtime JSON, and a versioned record.

Free percentage comes from `/usr/bin/memory_pressure`; the recorded
normal/warning/critical label is a documented classification of that percentage,
not a native Dispatch memory-pressure event. VM and compressor counters come
from `/usr/bin/vm_stat`; swap use comes from `sysctl vm.swapusage`. Peak
in-run deltas are kept because an end snapshot can miss recovered transient
pressure. Serial numbers, hardware UUIDs, usernames, unrelated command lines,
and prompt secrets are excluded.

Physical footprint is primary for purgeable-memory claims. RSS includes pages
that are explicitly reclaimable and can therefore move opposite to the memory
effect being studied. Runtime receipts separately record volatile transitions,
relocks, retained relocks, empty recoveries, invalidated slots, and cumulative
reloaded bytes; cumulative reload bytes are not interpreted as footprint.

In addition, a pinned native Swift helper subscribes to macOS
`DispatchSourceMemoryPressure`. Its JSONL stream begins before the model worker
and records any kernel-delivered normal, warning, or critical transitions with
monotonic time. Its release-binary SHA-256 is attached to every row. An absent
transition does not prove absence of pressure, so the event stream complements
rather than replaces compressor, swap, and free-percentage sampling.

## Admission policy

A measured row is rejected if it is a warmup, fails, times out, has runtime
errors, lacks a positive completion count or decode rate, lacks a response hash,
contains fewer than two valid pressure observations, crosses the configured 25%
free guard, grows swap by more than 384 MiB, or observes a native critical
pressure event. The experiment requires equal
response hashes across measured arms.

The pinned CLI does not expose generated token IDs. Accordingly,
`require_token_id_parity=false` is explicit in Gate 1; token-ID absence is a
documented runtime capability limitation, not silently ignored. Future adapters
that expose IDs must enable the stricter policy.

The admitted dataset is complete only if every scheduled measured row passes.
Analysis fails closed on an incomplete dataset. Failures are scientific outcomes
and are never silently retried.

## Safety and observer-effect controls

- No wired-memory, compressor, swap, jetsam, or kernel limits are modified.
- Live anonymous pressure is off for the primary sweep.
- A separate pressure worker, if later enabled, is capped at 4,096 MiB and 15%
  of physical memory, requires normal initial pressure, and stops before the
  model guard.
- A hard free-memory guard terminates the child process rather than risking a
  system-wide collapse.
- Exactly one canonical checkpoint is streamed once into a resumable packed
  artifact. The experiment never loads two model configurations concurrently.
- Cache alternatives are evaluated sequentially; an online controller must use
  trace-derived counterfactuals rather than probe by loading a competing model.

## After Gate 1

If Gate 1 does not pass repeatably, the joint pressure-controller claim is
rejected or narrowed; implementation does not continue by moving the threshold.
If it passes, traces are divided by whole workloads into training/validation/test
sets. The controller and its thresholds are frozen before the held-out test.

Required Gate-2 baselines are the best global fixed arm, best per-pressure fixed
arm, runtime default, controller without pressure, controller without route
telemetry, and the offline per-cell oracle. Required metrics include geometric
mean throughput, oracle fraction, fallback regret, transition count, safety
violations, compression/swap, and output parity.

## Publication scope

One Mac and one model can establish feasibility or a negative result, but not a
general Apple-Silicon systems claim. A main paper requires at least two MoE
architectures, three chip generations, independent reproduction, exact commands,
raw receipts, energy/thermal methodology, quality checks, and comparison with
strong resident and bounded-memory baselines.
