# Results ledger

Only automatically admitted results appear here. Scope labels are part of each
result and must accompany any quotation.

## R0 — Pinned Qwen runtime smoke

Status: **admitted functionality evidence; battery diagnostic; not Gate 1**

Timestamp: 24 August 2026 08:07 UTC

Admitted artifact SHA-256:
`e4e19475af63ae1c536a8b0433f608bcef8f35ab2383f03b18faa852398eda18`

Analysis artifact SHA-256:
`aff952b37ac3050ca7ed2ab5327236a7d2b2ad7cd3827fe76f3f80de94b64ce6`

The external verifier checked 47 packed files totaling 19,551,394,758 bytes.
The model source revision, runtime commit, manifest, source-index hash, receipt,
and release binaries are all recorded in the machine-local registration.

The smoke used one warmup and one measured row at 16 and 32 expert slots, a
60-token prompt, a 32-token greedy completion, 4,096-token context limit, and
seed 104729. Both measured rows were admitted; their response SHA-256 values
were identical; neither grew swap.

| Arm | Decode tok/s | Expert hit rate | Minimum free % | Peak compressor growth | Peak process-tree RSS |
|---|---:|---:|---:|---:|---:|
| 16 slots | 8.767 | 46.67% | 46% | 535.5 MiB | 1,244.7 MiB |
| 32 slots | 8.094 | 61.34% | 42% | 1,816.9 MiB | 2,014.9 MiB |

The 32-slot row increased hit rate by 14.67 percentage points but was 7.68%
slower. This is mechanistically consistent with the research hypothesis, but it
does **not** pass Gate 1: it has only one measured repetition per arm, ran on
battery, and the preregistered throughput gap is 15%. The automatic report says
`NOT PROVEN`.

## R1 — Six-arm AC-power Gate 1

Status: **v4 complete — NOT PROVEN**

Gate-1 v1 completed warmup rows at 16, 32, and 64 slots. Its 96-slot warmup
crossed the preregistered 128 MiB live swap-growth ceiling after 11 seconds
(207.5 MiB observed), with a minimum 33% free reading and no native warning or
critical transition. The process group was terminated; there were no measured
rows and therefore no Gate verdict. The event is retained as safety/pressure
evidence but cannot support the 15% claim.

V2 then stopped on its first 8-slot warmup before inference: Qwen's prefill tile
requires at least 16 expert slots. No performance observation or measured row was
produced. V3 replaces that invalid arm with 24 slots and changes nothing else.

V3 completed warmups from 16 through 64 slots. Hit rate rose from 48.98% to
81.17%, while warmup throughput fell from 10.584 to 9.497 token/s (10.27%). Its
96-slot warmup then grew swap by 476.4 MiB during prefill and was terminated by
the 384 MiB ceiling before decode. V4 introduces a separate 768 MiB warmup
ceiling but keeps the measured ceiling at 384 MiB. These warmups are diagnostic,
not admitted performance results.

V4 completed all six warmups and all 30 measured rows. Every measured row was
admitted, all outputs had one identical SHA-256, all power snapshots were AC,
and there were no native warning/critical events. Admitted artifact SHA-256:
`094d9f73549c332046fbfeb5459d2338c12ae5eb9494f473319a6a97b5910ab8`.

| Slots | Cache MiB | Median decode tok/s | Hit rate | Median minimum free % | Median peak compressor growth |
|---:|---:|---:|---:|---:|---:|
| 16 | 1,136 | 11.330 | 48.98% | 51% | 714.8 MiB |
| 24 | 1,704 | 11.329 | 57.15% | 49% | 1,245.6 MiB |
| 32 | 2,272 | 11.001 | 63.73% | 47% | 1,643.9 MiB |
| 48 | 3,408 | 10.495 | 73.87% | 43% | 3,158.4 MiB |
| 64 | 4,544 | 10.177 | 81.17% | 40% | 3,766.3 MiB |
| 96 | 6,816 | 10.120 | 90.13% | 32% | 5,830.0 MiB |

The strongest pair was 16→96 slots. Its aggregate median slowdown was 10.68%;
the paired median was 10.54%, with per-repetition gaps of 10.72%, 10.84%,
10.54%, 9.45%, and 8.94%. A deterministic bootstrap 95% interval for the paired
median was 8.94–10.84%. Directional support was 5/5, hit rate improved 41.15
percentage points, and minimum free memory fell 19 points.

**Verdict:** the non-monotonic mechanism is real and repeatable, but the frozen
15% Gate threshold was not met. The original expert-cache-only controller paper
is stopped. These results support a scoped characterization/negative-result
paper and motivate a new, independently gated research direction; they do not
support a breakthrough claim.

## R2 — Layerwise reload-correct purgeable expert cache

Status: **admitted single-host/single-model systems result; generalization pending**

The successor mechanism is materially different from the rejected cache-size
controller. Each routed-expert slot is a Metal-owned shared buffer. At an
already-synchronized layer/token boundary, the hottest 16 of 96 logical slots
remain nonvolatile and the cold remainder becomes purgeable. Every potential
hit is relocked before GPU binding. If Metal returns `.empty`, the slot identity
is invalidated and exact bytes are read from the immutable packed layer file.

Committed executor:
`ec84269d5ce162a0376099d39b30dd19aa99f096` (parent upstream
`01f7d5e774ca940982ea3aa012bd880b5c9d634e`). Candidate binary SHA-256:
`f984bc9b2e25a2a9174921c2e02757037bca0a12dd85da974d7123af8eee8eed`.
Rebuilt upstream binary SHA-256:
`38f59684ed1b33515da717398018b87f6d844b212523b68b4bffa0e4a5f579eb`.

### R2a — 4 GiB controlled co-tenant pressure

V6 used a fresh held-out prompt, one excluded warmup, five balanced measured
triples, 256 generated tokens, AC power, and the safety-bounded 4 GiB pressure
worker. All 15 measured rows were admitted and produced one response hash.
Admitted artifact SHA-256:
`5b23799f865385ceaf09aef5b4200d7c1da45e97170e01486e7bcaa641bfa0ad`.

| Arm | Decode tok/s | Hit rate | Peak footprint | Peak compressor | Min free |
|---|---:|---:|---:|---:|---:|
| Upstream fixed 16 | 13.025 | 47.91% | 1.374 GiB | 0.675 GiB | 57% |
| Upstream fixed 96 | 12.116 | 90.81% | 6.705 GiB | 5.890 GiB | 38% |
| ElasticUMA 96 / hot 16 | 14.136 | 86.83% | 4.584 GiB | 0.840 GiB | 44% |

Against upstream-96, ElasticUMA's paired median gain was 13.67%, with a
deterministic bootstrap 95% interval of 5.33–33.91% gain. Peak physical
footprint fell 31.64% and peak compressor growth fell by 5.05 GiB. Against the
strong small-memory upstream-16 policy, the paired median gain was 7.25%; the
interval ranged from 5.02% slower to 24.08% faster. ElasticUMA retained 38.92
additional hit-rate points. All five candidate rows observed nonzero exact
recovery and no arm grew swap.

### R2b — no synthetic pressure

V7 repeated the three-arm protocol with another unseen prompt and no pressure
worker. All 15 measured rows were admitted and produced one response hash.
Admitted artifact SHA-256:
`06b78c1f2473256c7067dc05bf63c974d863bec22edf2cda9dc0b36e4527fa8e`.

| Arm | Decode tok/s | Hit rate | Peak footprint | Peak compressor | Min free |
|---|---:|---:|---:|---:|---:|
| Upstream fixed 16 | 14.520 | 49.82% | 1.386 GiB | 0 GiB | 57% |
| Upstream fixed 96 | 14.293 | 90.58% | 6.721 GiB | 5.991 GiB | 38% |
| ElasticUMA 96 / hot 16 | 16.807 | 87.50% | 4.594 GiB | 0.700 GiB | 44% |

ElasticUMA beat both upstream baselines in every pair. Paired median gains were
16.91% over upstream-16 (95% interval 4.56–38.79%) and 17.59% over
upstream-96 (4.79–29.15%). It reduced fixed-96 peak footprint 31.65% and peak
compressor growth by 5.29 GiB. No arm grew swap.

### Interpretation boundary

This is a real Pareto improvement on the measured M1 Max/Qwen3.6 workloads: the
candidate retains most large-cache locality, avoids its pressure collapse, and
beats the smallest fixed cache. It is not yet an “all Macs/models” result. The
controlled co-tenant is synthetic; energy is unmeasured; only one architecture,
host, batch size, and context regime have admitted data; no independent
reproduction exists yet. RSS is secondary because it includes reclaimable
pages; process memory claims use `proc_pid_rusage().ri_phys_footprint`.

## R3 — Qwen3.8-27B dense control diagnostic

Status: **incomplete/rejected under the frozen sustained-run safety gate**

The canonical `mlx-community/Qwen3.8-27B-4bit` snapshot is stored once at
revision `3e6447f082e89cc7f0bc6e5441afd38dfce760ff` and run locally with
MLX 0.32.1 / mlx-vlm 0.6.14. One warmup and one measured 128-token row completed;
the measured row reported 11.36 token/s, 17.96 GiB sampled peak physical
footprint, 18.60 GiB MLX peak memory, 20% minimum free memory, and 151 MiB swap
growth. A subsequent row crossed the frozen 20% free-memory guard at 19% and
was terminated, so no complete admitted five-row dataset exists. These numbers
are diagnostic only and cannot be used as a controlled speed comparison with
the MoE model.

## R4 — Gemma 4 second-architecture validation

Status: **admitted single-host cross-model evidence**

Gemma 4 26B-A4B IT Q4 was streamed once into a verified 37-file packed artifact
at revision `0d77464eeb233a2da68ebf9d7dc4edaac7db956d` (14,291,915,755 verified
bytes). V8 used a fresh model-specific prompt, 128 generated tokens, one excluded
warmup, and five balanced measured triples without a pressure worker. All 15
measured rows were admitted with one output hash. Admitted artifact SHA-256:
`2b1c312e5660539c350082ca70ef65e8a93c6ee958ef947e8478598a4cba0a9e`.

| Arm | Decode tok/s | Hit rate | Peak footprint | Peak compressor | Min free |
|---|---:|---:|---:|---:|---:|
| Upstream fixed 16 | 16.394 | 65.52% | 1.986 GiB | 0 GiB | 69% |
| Upstream fixed 96 | 18.742 | 98.40% | 8.538 GiB | 5.114 GiB | 50% |
| ElasticUMA 96 / hot 16 | 23.820 | 95.79% | 5.527 GiB | 1.073 GiB | 55% |

ElasticUMA won every pair. Its paired median gain was 45.30% over upstream-16
(bootstrap 95% interval 23.45–51.44%) and 26.01% over upstream-96
(11.88–28.55%). It reduced fixed-96 peak physical footprint 35.26% and peak
compressor growth 4.04 GiB, while retaining 30.28 hit-rate points over the
small-cache baseline. Every candidate row observed exact empty recovery and no
arm grew swap.

This demonstrates transfer across Qwen3.6 (256 experts, 40 layers) and Gemma 4
(128 experts, 30 layers) on the same host. It does not establish cross-chip
generality; Qwen and Gemma also used different model-appropriate prompts and
generation lengths, so their absolute token/s values are not compared as a
model benchmark.
