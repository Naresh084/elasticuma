# Reload-correct purgeable expert caching on Apple UMA

Status: experimental research implementation. Qwen3.6 pressure/no-pressure and
Gemma 4 no-pressure protocols pass on one M1 Max. It is a two-architecture,
single-host result; cross-generation and independent reproduction remain open.

## Problem

A fixed routed-expert cache competes with the filesystem cache, KV state, the
GPU, and every other process for the same Apple unified-memory pool. More expert
slots can improve logical hit rate while making end-to-end inference slower by
driving compression and page displacement. A useful cache therefore needs to be
large when memory is available and cheaply reclaimable when it is not.

## Mechanism

Each expert slot is a Metal-owned `storageModeShared` buffer. At a GPU-safe
boundary the runtime keeps the hottest slots nonvolatile and calls
`setPurgeableState(.volatile)` on the cold remainder. macOS may reclaim those
pages rather than compressing or swapping them.

The cache never trusts a volatile hit. Before binding a matching slot, planning
calls `setPurgeableState(.nonVolatile)` under the cache lock:

- a retained return preserves the hit;
- `.empty` invalidates the slot's expert identity and converts the access to a
  normal `pread` miss;
- the buffer is rebound only after the exact expert bytes have been reloaded.

The transition runs after every synchronized prefill layer and after a complete
decode step. This prevents the full logical cache from becoming resident during
prefill before it is first offered to the OS. The fixed mode does not execute
any purgeability path.

Important invariants:

1. A volatile resource is never consumed without a nonvolatile relock.
2. `.empty` content is never treated as a hit.
3. Purge transitions occur only after all GPU reads of the affected slots have
   completed.
4. Slot identity, LFU/recency state, residency state, and recovery counters are
   serialized by the same cache lock.
5. Model files remain immutable and single-copy; recovery uses positional reads
   from the already-open packed layer file.

## Controls

CLI:

```text
--expert-cache-slots 96
--expert-cache-residency os-managed
--expert-cache-hot-slots 16
```

The server exposes the same three controls. `fixed` remains the default for
backward compatibility. The CLI emits an `expert-residency` receipt containing
the hot-slot target, volatile transitions, relocks, retained relocks, empty
recoveries, explicit discards, invalidated slots, and recovered bytes.

## Early frozen implementation gate (V5)

Protocol: Qwen3.6-35B-A3B Q4, pinned packed model and runtime, Apple M1 Max
(24-core GPU, 32 GiB), AC power, 4 GiB safety-bounded co-tenant allocation,
256 generated tokens, one excluded warmup and five Latin-balanced measured
pairs. The prompt was unseen before the mechanism and thresholds were frozen.
All ten measured rows were admitted and produced one output SHA-256.

| Metric | Fixed 96 slots | OS-managed 96 / hot 16 | Effect |
| --- | ---: | ---: | ---: |
| Median decode | 11.861 tok/s | 13.977 tok/s | 17.8% aggregate gain |
| Paired throughput | — | — | 16.1% median gain |
| Paired bootstrap 95% interval | — | — | 6.5–40.0% gain |
| Peak physical footprint | 6.657 GiB | 4.430 GiB | 33.46% lower |
| Peak compressor growth | 5.848 GiB | 1.004 GiB | 4.844 GiB lower |
| Minimum free memory | 37% | 44% | +7 points |
| Median effective expert hit rate | 91.77% | 88.77% | -3.00 points |
| Peak swap growth | 0 | 0 | equal |

Every candidate row observed non-zero `.empty` recovery (4,774–5,825 events)
and 7.87–9.60 GiB of cumulative exact reloads. Cumulative reload bytes count
repeated reclamation and are not a footprint measurement.

Later final protocols compare the committed patch with untouched upstream
fixed-16 and fixed-96 binaries. Qwen V6/V7 and Gemma V8 admit 45/45 positive
rows with within-protocol output parity. The final paper reports paired median
gains and fixed-96 footprint reductions; [the result ledger](../../docs/RESULTS.md)
carries exact values, intervals, and artifact hashes.

## Claim limits and open validation

- The evidence establishes a strong local systems result against the same
  runtime with fixed Metal-owned slots. It does not yet establish superiority
  over every Mac runtime.
- The 4 GiB co-tenant is controlled and safety-bounded, not a trace of a real
  desktop workload.
- Later Apple generations, long-context/concurrent desktop traces, energy, and
  an independent operator remain required for a general Apple claim.
- RSS includes reclaimable pages and is reported only as secondary telemetry;
  `proc_pid_rusage().ri_phys_footprint` is the primary process memory measure.
- The upstream suite currently has five pre-existing `RepackCLITests` failures:
  those tests seek `TurboFieldfareRepack` while the package builds
  `slipstream-repack`. The other 588 tests, including all new cache, inference,
  CLI, and server tests, pass.
