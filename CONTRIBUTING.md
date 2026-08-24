# Contributing to ElasticUMA

Thanks for helping improve local MoE inference on Apple Silicon. Correctness,
claim discipline, and reproducibility matter more than the size of a reported
speedup.

## Before opening an issue

- Search existing issues and [the live claim ledger](docs/CLAIMS.md).
- Run `uv run elasticuma doctor` and include only its privacy-safe fields.
- State the Mac chip, RAM, macOS, Swift, ElasticUMA commit, exact checkpoint and
  revision, exact command, complete error/log, and whether another model process
  was running.
- Never post serial numbers, hardware UUIDs, credentials, private prompts, model
  weights, or unrelated process command lines.

## Pull requests

1. Keep one mechanism or model boundary per PR.
2. Explain the hypothesis and what evidence would falsify it.
3. Add or update fast tests before collecting expensive model evidence.
4. Run `make check` and include the result.
5. Preserve fixed-mode behavior unless the PR explicitly changes that baseline.
6. Do not silently retry, delete, or edit raw experiment rows.

### Performance changes

Include same-model A/B end-to-end measurements on the base and proposed commits:

- hardware, RAM, OS, Swift, power mode, and thermal deviations;
- checkpoint repo, immutable revision, quantization, and model license;
- exact commands, prompt hash, context, generation length, and balanced order;
- all measured repetitions, not only the best run;
- decode throughput, TTFT when relevant, physical footprint, compression/swap,
  output parity, and guard failures; and
- negative or regressing workloads.

A result remains `raw` until the configured admission checks pass. Do not put
raw or projected numbers in the README headline or paper abstract.

### Model support

A JSON catalog profile is enough only for a checkpoint already supported by the
native architecture path. New architectures require the complete checklist in
[docs/models.md](docs/models.md), numerical fixtures, deterministic parity, and
a held-out protocol. Keep `verification: community` until evidence is admitted.

### AI-assisted contributions

AI assistance is welcome, but a human contributor must understand, test, and be
able to explain every change. Do not submit invented APIs, fabricated benchmark
receipts, or citations you have not checked. The human contributor is
responsible for license compliance and any required disclosure.

## License

Contributions are accepted under the repository's Apache License 2.0. Changes to
the bundled upstream patch must preserve all applicable upstream notices.
