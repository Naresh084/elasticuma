# Install ElasticUMA

## Requirements

- Apple-Silicon Mac (`arm64`)
- macOS 26+
- Xcode 26 / Swift 6.2+
- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- Git
- 32 GiB RAM for the admitted Qwen3.6 and Gemma 4 profiles

Check the toolchain first:

```bash
uname -sm
sw_vers -productVersion
swift --version
python3 --version
uv --version
```

## Install from source

```bash
git clone https://github.com/Naresh084/elasticuma.git
cd elasticuma
uv sync --extra dev --locked
uv run elasticuma --version
```

ElasticUMA currently ships as a source-first research release because the
native Swift/Metal runtime is reconstructed from a pinned upstream commit and a
reviewable patch. A future wheel must preserve the same provenance checks.

## Build the native runtime

```bash
uv run elasticuma runtime install
uv run elasticuma runtime status
```

The installer:

1. clones the pinned upstream runtime into `.runtime/elasticuma`;
2. verifies the bundled patch SHA-256;
3. applies the patch to the pinned Git index;
4. rejects unstaged, untracked, or extra source changes; and
5. builds `slipstream-repack`, `slipstream`, and `slipstream-server` in release
   mode.

The command is idempotent. It rebuilds from the existing verified checkout and
does not clone another runtime on every invocation.

## Verify the host

```bash
uv run elasticuma doctor
```

`serve_ready` becomes true after the native build. `research_ready` additionally
requires the optional native pressure monitor used by paper experiments.
Hardware output deliberately omits serial numbers and hardware UUIDs.

## Model storage

Models live outside the repository in one canonical cache:

```text
~/Library/Caches/elasticuma/
```

Override it only when necessary:

```bash
export ELASTICUMA_CACHE_ROOT=/Volumes/FastSSD/elasticuma
```

Safety defaults:

- `ELASTICUMA_DISK_RESERVE_GIB=100`
- `ELASTICUMA_MAX_MODEL_GIB=80`
- `ELASTICUMA_STORE_LIMIT_GIB=120`

Every install holds a global download lock. Preflight searches common Hugging
Face caches for the exact pinned revision and reuses a complete match rather
than downloading it again. It refuses a second full transfer when the current
repacker cannot consume an already-present source snapshot safely.

## Install a catalog model

```bash
uv run elasticuma model catalog
uv run elasticuma model preflight --profile qwen36
uv run elasticuma model install --profile qwen36
```

Never skip preflight. If `allowed` is false, fix the reported disk, runtime, or
duplicate-snapshot condition instead of forcing the transfer.

## Verify the installation

```bash
uv run elasticuma model catalog
uv run elasticuma model list
uv run elasticuma run \
  --model qwen36 \
  --prompt "Reply with exactly: ElasticUMA is ready." \
  --max-new 16
```

Continue with [quickstart.md](quickstart.md).

## Troubleshooting

### Xcode license or toolchain errors

Open Xcode once, accept its license, and confirm `xcode-select -p` points to the
intended installation. ElasticUMA does not modify the selected toolchain.

### Runtime checkout contains extra changes

The bootstrap fails closed instead of overwriting source. If the checkout is
disposable, move `.runtime/elasticuma` aside and rerun the installer. Preserve
any intentional work first.

### Model already exists elsewhere

Preflight reports the matching snapshot path. Do not start another download.
Either use the registered packed model already present or implement a reviewed
local-source repack path for that format.

### Another model process is running

ElasticUMA never terminates it. Stop the process yourself only if you own it,
then rerun the command.
