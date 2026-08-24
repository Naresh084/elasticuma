# Reproduction protocol

## Supported starting point

The current artifact targets macOS on arm64 and requires Swift 6.2/Xcode 26 or a
compatible compiler, Python 3.11+, `uv`, Git, and roughly 20 GiB of model storage
while preserving the configured 100 GiB disk reserve. The first development host
is an M1 Max/32 GB; other Macs are welcome but must retain their own hardware
receipt and experiment name.

## 1. Create the environment

```bash
git clone https://github.com/Naresh084/elasticuma.git
cd elasticuma
uv sync --extra dev
make check
make native
uv run elasticuma doctor --json
```

`doctor` deliberately omits serial numbers and hardware UUIDs.

## 2. Recreate the pinned runtime

```bash
uv run elasticuma runtime install
```

The public bootstrap verifies and applies the bundled patch to the pinned
upstream commit, rejects every additional source change, and builds the repacker,
CLI, and server. For paper baseline reproduction, build an independent untouched
upstream checkout separately:

```bash
make runtime-upstream
```

Do not replace the untouched `.runtime/slipstream` baseline with the patched
`.runtime/elasticuma` candidate. See `docs/DECISIONS.md` for the known upstream
debug-product test-name mismatch.

## 3. Preflight the single model artifact

```bash
uv run elasticuma model preflight --profile qwen36
```

Read `allowed`, `reasons`, `source_snapshot_elsewhere`, `disk_free_gib`, and
`disk_reserve_gib`. Do not continue on a refusal. The tool detects a complete
source snapshot in common Hugging Face caches so it cannot silently download a
second source copy.

## 4. Perform one resumable streaming install

```bash
uv run elasticuma model install --profile qwen36
```

The command acquires a global cache lock and streams from the pinned source into
one canonical `.gturbo` directory. On interruption, run the identical command;
it adds the upstream `--resume` flag to the existing partial. Never use
`elasticuma model hf-fetch` for this packed Qwen experiment because that would keep
an additional source snapshot.

## 5. Smoke test before the full grid

Use `scripts/smoke_qwen36.sh`. It generates a short deterministic response with
the smallest cache and validates the structured runtime receipt. Do not launch
the full matrix until smoke output, telemetry parsing, and free-memory guards
have been manually inspected.

## 6. Run Gate 1

Close heavy applications, connect power, record power mode and ambient context,
and avoid interacting with the machine during a sweep.

```bash
make gate1
uv run elasticuma experiment run --config configs/gate1.v4.example.toml
uv run elasticuma experiment analyze \
  --input artifacts/admitted/gate1-m1max-qwen36-q4-v4.json
```

The run is intentionally long: six warmups and thirty measurements. It never
silently resumes in the middle because selective retry would compromise the
balanced schedule. A failed sweep receives a new experiment name after the
cause is documented.

## 7. Verify artifact integrity

```bash
make check
git status --short
find artifacts/raw/gate1-m1max-qwen36-q4-v4 -name record.json | wc -l
jq '.complete, .measured_count, .admitted_count' \
  artifacts/admitted/gate1-m1max-qwen36-q4-v4.json
```

## 8. Reproduce the purgeable-cache result

Use fresh experiment names if canonical V6/V7 artifacts already exist; the
runner refuses to append or retry an immutable experiment directory.

```bash
uv run elasticuma experiment run \
  --config configs/purgeable.pressure.example.toml
uv run elasticuma experiment run \
  --config configs/purgeable.nopressure.example.toml
```

Each protocol runs three excluded warmups and fifteen measured rows. Confirm one
output hash, executor binary hashes, AC power, complete admission, nonzero
candidate empty recovery, and no critical/swap violation. Primary process memory
is `phys_footprint_bytes`, not RSS.

The optional dense control requires an isolated Python 3.12 environment with
`mlx-vlm==0.6.14`, `mlx==0.32.1`, and `jinja2==3.1.6`. It reuses the canonical
Qwen3.8 snapshot in offline mode. The current M1 Max run crossed its frozen
free-memory guard and is diagnostic, not an admitted baseline.

The tracked `artifacts/releases/elasticuma-paper-v1.tar.gz` is the redacted
paper artifact and verifies independently with its internal `SHA256SUMS`. To
rebuild that archive, first reproduce the required raw/admitted experiments in
their ignored local directories, then run:

```bash
uv run python scripts/build_paper_release_bundle.py \
  --output artifacts/releases/elasticuma-paper-v1
```

The tracked `.tar.gz` contains raw/admitted evidence, analyses, figures,
reproduction code, pinned manifests, and the native patch—but no model weights,
build products, secrets, or machine-local paths.

Recreate analysis from the admitted JSON. Never edit the generated table by
hand. A public artifact release should include raw/admitted receipts and hashes,
but exclude model files, runtime build products, user paths, and secrets.

## Reproduction report

Report the Git commit, model/runtime revisions, safe doctor output, whether the
machine was idle and plugged in, exact command, admitted artifact hash, Gate-1
verdict, and any deviations. A different result is useful; do not tune until it
matches the original.
