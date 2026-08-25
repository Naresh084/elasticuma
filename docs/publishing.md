# Publish this repository on GitHub

The prepared local repository is the `elasticuma-github` checkout. It contains
tracked source and public artifacts only. Models, raw local runs,
virtual environments, runtime checkouts, build products, locks, and secrets are
ignored and absent from Git history.

## Pre-push verification

```bash
make check
uv build
git status --short
git ls-files | rg '\.(safetensors|gturbo|bin|pyc)$' && exit 1 || true
git log -1 --show-signature --format=fuller
```

`git status --short` must be empty after the final commit.

## Create and push

Create an empty public repository named `elasticuma` under `Naresh084` without
adding a generated README, license, or `.gitignore`.
Then:

```bash
git remote add origin https://github.com/Naresh084/elasticuma.git
git push -u origin main
git tag -a v0.2.0 -m "ElasticUMA public research release v0.2.0"
git push origin v0.2.0
```

This document does not perform those external writes. Review the final diff and
repository visibility before pushing.

## GitHub release assets

Attach these existing tracked files to release `v0.2.0`:

- `paper/ElasticUMA-paper.pdf`
- `artifacts/releases/elasticuma-paper-v1.tar.gz`

The evidence archive contains its own manifest and `SHA256SUMS`; it contains no
model weights or runtime build products.

## Recommended repository settings

- Enable Issues and private vulnerability reporting.
- Keep Actions permissions read-only by default.
- Require the `unit` and `linux-contract` CI jobs before merging.
- Enable squash merging and branch deletion after merge.
- Add topics: `apple-silicon`, `metal`, `mixture-of-experts`, `local-llm`,
  `unified-memory`, `swift`.
- Do not enable Git LFS for the current repository; every tracked artifact is
  small enough for ordinary Git.
