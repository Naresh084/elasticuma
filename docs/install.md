# Install

## Requirements

- Apple-Silicon Mac (`arm64`)
- macOS 26 or newer
- Xcode 26 / Swift 6.2 or newer
- Python 3.11+
- Git
- [uv](https://docs.astral.sh/uv/)

The two verified model profiles were measured on a 32 GiB M1 Max. Smaller or
larger Macs may have different usable model and context limits.

## Install from source

```bash
git clone https://github.com/Naresh084/elasticuma.git
cd elasticuma
./install.sh
```

`install.sh` runs `uv sync --locked`, clones the pinned native runtime under the
canonical ElasticUMA cache, verifies both runtime patches and their combined
staged diff, and builds the CLI, server, decode service, and Mac app. Rerunning
it reuses the verified checkout.

Check readiness:

```bash
uv run euma doctor
uv run euma models
```

Open the native app:

```bash
uv run euma app open
```

## Install a model

```bash
uv run euma setup qwen36
```

For automation, use `--yes` only after reviewing the dry run:

```bash
uv run euma setup qwen36 --dry-run
uv run euma setup qwen36 --yes
```

## Model storage

Models stay outside the repository in one canonical cache:

```text
~/Library/Caches/elasticuma/
```

Move it to another disk only when needed:

```bash
export ELASTICUMA_CACHE_ROOT=/Volumes/FastSSD/elasticuma
```

Safety defaults:

- keep at least 100 GiB free after a transfer;
- refuse a single published model above 80 GiB;
- limit the complete ElasticUMA model store to 120 GiB; and
- reuse matching snapshots from common Hugging Face cache locations.

Override the limits with `ELASTICUMA_DISK_RESERVE_GIB`,
`ELASTICUMA_MAX_MODEL_GIB`, and `ELASTICUMA_STORE_LIMIT_GIB` only when you have
reviewed the planned storage use.

## Troubleshooting

### Missing Swift or Xcode

Open Xcode once, accept its license, and check `swift --version` and
`xcode-select -p`.

### Runtime checkout changed

ElasticUMA refuses to overwrite an altered runtime tree. Preserve intentional
work, move the ignored `.runtime/elasticuma` directory aside, and rerun
`./install.sh`.

### Existing model snapshot found

The preflight intentionally refuses a second full transfer when it cannot safely
reuse an existing source snapshot. Keep the existing copy and use or repack it;
do not delete it merely to satisfy setup.

### Another model server is running

Stop it yourself only if you own it. ElasticUMA does not terminate unrelated
processes.
