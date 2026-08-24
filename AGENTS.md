# ElasticUMA research rules

These instructions apply to the whole repository.

## Claim discipline

- Never place an unmeasured number in the abstract, README headline, paper
  results, release notes, or comparison table.
- Label a result `raw`, `admitted`, `diagnostic`, or `projected`.
- Only `admitted` results may support a paper claim.
- Keep dense Qwen3.8 separate from MoE capacity claims.
- Do not describe inherited mechanisms as ElasticUMA contributions.

## Experiment discipline

- Pin model, revision, runtime commit, quantization, prompt hash, OS, compiler,
  power mode, and command.
- One model worker at a time. Acquire the repository model lock before load.
- Use warmup plus ABBA or randomized balanced order.
- Never silently retry a failed row. Record the failure and change the
  hypothesis or implementation first.
- Raw receipts are append-only. Corrections produce a new run ID.
- Fail closed on missing output hashes, token counts, memory samples, or
  process-overlap evidence.

## Storage discipline

- Use the canonical cache reported by `elasticuma doctor`; inspect registrations
  with `elasticuma model list`.
- Never invoke a second Hugging Face cache or copy a snapshot into the repo.
- Resolve revisions before download and reuse matching existing snapshots.
- Enforce the disk reserve and total-store limit before every transfer.
- Do not delete models or caches without explicit user approval.

## Safety

- Pressure generation requires an explicit CLI opt-in and a bounded MiB value.
- Stop pressure/model workers when free percentage crosses the configured guard.
- Do not modify macOS wired-memory, swap, compressor, or jetsam configuration.
- Never collect or publish serial numbers, hardware UUIDs, usernames, prompt
  secrets, credentials, or unrelated process command lines.

## Code standards

- Python is orchestration only; no Python object work in a future per-layer hot
  path.
- Parsers must have fixtures and fail on ambiguous input.
- Use atomic writes for manifests and admitted artifacts.
- Public APIs use typed dataclasses and versioned JSON schemas.
- Run `make check` before every commit.
