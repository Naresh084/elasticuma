# Native runtime reconstruction

ElasticUMA does not vendor or silently fork an inference engine. The public
bootstrap reconstructs the exact measured implementation from:

- upstream: <https://github.com/dwijenpatel/slipstream>
- upstream commit: `01f7d5e774ca940982ea3aa012bd880b5c9d634e`
- patch: `patches/elasticuma-purgeable.patch`
- measured code commit represented by the patch:
  `ec84269d5ce162a0376099d39b30dd19aa99f096`
- patch SHA-256:
  `dc0418cb83988d1679796af1d707dbdb03db8473fcff9c45e6ec52daee8dc850`

Build it with:

```bash
uv run elasticuma runtime install
```

The installer stages the patch in the cloned Git index. On every invocation it
hashes the complete staged binary diff and refuses unstaged, untracked, or extra
source changes. Build products and the checkout stay under ignored `.runtime/`.

The patch adds Metal-owned expert slots, nonvolatile/volatile/empty state,
relock-before-hit validation, exact positional reload, GPU-safe prefill/decode
transitions, telemetry, CLI/server flags, and focused tests. See
[`docs/ELASTICUMA_PURGEABLE_CACHE.md`](docs/ELASTICUMA_PURGEABLE_CACHE.md).

The immutable paper evidence archive retains patch SHA-256
`9a6f137e56b9e76398657a54deae7bcbbd106592a9293be18d8162c1e5f72745`,
the exact bundle produced with the experiments. The public patch SHA differs
only because its Markdown documentation corrects binary-unit labels and adds
the final Gemma/Qwen scope; the measured Swift code is the same `ec84269` code.

The upstream and patch are Apache-2.0. Keep upstream copyright and attribution
notices when redistributing a reconstructed source tree. See the repository
`NOTICE` and `docs/THIRD_PARTY.md`.
