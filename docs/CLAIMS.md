# Evidence and claim ledger

Evidence cutoff: 24 August 2026

This ledger is the authority for project claims. A statement may move from a
hypothesis to a measured result only when its evidence artifact is linked here,
passes automatic admission, and survives a manual audit of the raw receipts.

## Status vocabulary

| State | Meaning | May appear as a paper result? |
|---|---|---:|
| Hypothesis | Testable statement with no project measurement yet | No |
| Raw | Produced by a run but not admitted | No |
| Admitted | Passed the preregistered automatic checks | Yes, with scope |
| Reproduced | Admitted independently on another machine/operator | Yes |
| Rejected | Failed a gate or was contradicted | Only as a negative result |
| Projected | Analytical estimate, never a measurement | No |

## Current ledger

| ID | Claim | State | Required evidence | Current evidence |
|---|---|---|---|---|
| C0 | The pinned slipstream runtime can execute the exact pinned Qwen3.6-35B-A3B Q4 artifact on the M1 Max/32 GB test host. | Admitted (functionality scope) | Verified install receipt, successful deterministic smoke run, hardware receipt | 47-file install verification plus complete two-arm smoke; see `RESULTS.md` |
| C1 | Increasing the explicit expert-cache budget can raise hit rate while reducing decode throughput by at least 15% under independently observed unified-memory pressure. | Rejected for the preregistered M1 Max/Qwen workload | Six-point balanced sweep; at least five admitted repetitions per arm; deterministic output parity; pressure telemetry | V4 admitted all 30 measured rows; strongest paired median gap was 10.54%, below 15% |
| C2 | A causal, online-available pressure signal predicts the safer/faster cache choice before destructive swap thrash. | Not authorized | Held-out traces, preregistered predictor, lead-time and false-transition analysis | C1 failed; a materially different hypothesis and new gate are required |
| C3 | ElasticUMA beats the strongest fixed policy by at least 15% geometric-mean throughput while reaching at least 90% of an offline oracle and never falling more than 5% below the safe fallback. | Not authorized | Multi-workload controlled evaluation and ablations | Original controller path stopped at Gate 1 |
| C4 | ElasticUMA serves a checkpoint at least 1.5 times installed RAM at at least 5 token/s without target-model semantic changes. | Hypothesis | A materially over-RAM MoE, exact-mode receipts, stable long run | Not started |
| C5 | The result generalizes across two MoE architectures and three Apple generations. | Partially supported | Independent admitted datasets | Qwen3.6 and Gemma 4 pass on one M1 Max; other Apple generations and independent reproduction are not started |
| C6 | On the M1 Max/Qwen3.6 workload, layerwise OS-managed 96-slot caching preserves exact output, beats both upstream fixed-16 and fixed-96 policies, and reduces fixed-96 footprint/pressure damage. | Admitted (single-host/model scope) | Committed executor and binary hashes; fresh held-out pressure and no-pressure datasets; five paired repetitions; exact output; `ri_phys_footprint`; purge-recovery receipts | V6 and V7 each admitted 15/15 measured rows. See `RESULTS.md` |
| C7 | Qwen3.8-27B Q4 is a practical dense control on this 32 GB host. | Rejected as a sustained admitted control under the frozen safety protocol | Five complete 128-token rows without guard violations | One warmup and one measured row completed at ~18 GiB footprint; a later row crossed the 20% free-memory guard, so no complete admitted dataset exists |
| C8 | The purgeable-cache result transfers to Gemma 4 26B-A4B without model-specific tuning. | Admitted (single-host scope) | One-copy verified Gemma install and fresh admitted fixed/selective experiments | V8 admitted 15/15 rows; candidate won every pair and reduced fixed-96 footprint 35.3% |

## Facts that are not contributions

- The project uses a third-party Apache-2.0 runtime for native Metal execution
  and storage-backed routed experts. ElasticUMA does not claim those mechanisms.
- Expert caching, CPU/GPU offload, SSD-backed experts, bit slicing, native Metal
  kernels, speculative decoding, and kernel-managed caches all have direct prior
  art. See [PRIOR_ART.md](PRIOR_ART.md).
- Qwen3.8-27B is a dense control model. It cannot support an MoE capacity claim.
- A cache hit-rate improvement is not itself a speed or memory-safety result.
- An arXiv upload is dissemination, not peer review.

## Promotion checklist

A result number is promotable only when all boxes are satisfied:

- [ ] Immutable model and runtime revisions are recorded.
- [ ] Exact command, prompt hash, seed, compiler, OS, and safe hardware fields exist.
- [ ] The scheduled number of warmups and measured repetitions completed.
- [ ] No model processes overlapped.
- [ ] All measured rows passed return-code, timeout, token-count, throughput,
      memory-sampling, free-memory, and swap-growth checks.
- [ ] Deterministic response hashes match when the experiment requires parity.
- [ ] A token-ID hash matches when the runtime exposes token IDs and the policy
      requires it.
- [ ] The result is computed from the admitted artifact, not terminal output.
- [ ] Raw receipts and the analysis program reproduce the table or figure.
- [ ] Limitations and negative cells are retained.

## Disallowed shortcuts

- Multiplying unrelated microbenchmark gains into an end-to-end claim.
- Selecting only the fastest repetition or deleting failed rows.
- Retrying an unchanged failed hypothesis until one run passes.
- Comparing different checkpoints or quantizations in a controlled speed table.
- Calling an estimate, model-card number, or upstream result an ElasticUMA result.
