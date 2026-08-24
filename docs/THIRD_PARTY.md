# Third-party components

ElasticUMA keeps research orchestration separate from inference engines and
model artifacts. None of the following is presented as original project code.

## slipstream

- Source: <https://github.com/dwijenpatel/slipstream>
- Pinned commit: `01f7d5e774ca940982ea3aa012bd880b5c9d634e`
- License: Apache License 2.0
- Use: native Apple-Silicon Qwen/Gemma inference, streaming repacker, expert
  cache, API server, runtime timing, and cache counters
- Location: `.runtime/elasticuma` (ignored; recreated by bootstrap)
- Modification status: pinned upstream plus
  `runtime/patches/elasticuma-purgeable.patch`; the full staged diff SHA-256 is
  verified before every build

Release-binary hashes and the exact commit are captured in the registered model
manifest. The upstream test deviation is recorded in `DECISIONS.md`.

The patch and upstream source are Apache-2.0. ElasticUMA does not redistribute a
compiled runtime binary or a complete upstream source copy.

## Qwen3.6-35B-A3B 4-bit MLX checkpoint

- Source: <https://huggingface.co/mlx-community/Qwen3.6-35B-A3B-4bit>
- Pinned revision: `38740b847e4cb78f352aba30aa41c76e08e6eb46`
- Use: primary development MoE
- Local location: canonical user cache, never in Git

The model's own license and acceptable-use terms apply independently. The
registered receipt records provenance; no model weights are distributed by this
repository.

## Gemma 4 26B-A4B 4-bit MLX checkpoint

- Source: <https://huggingface.co/mlx-community/gemma-4-26b-a4b-it-4bit>
- Pinned revision: `0d77464eeb233a2da68ebf9d7dc4edaac7db956d`
- Use: second admitted MoE architecture
- Local location: canonical user cache, never in Git

The model's Apache-2.0 license and model-card terms apply independently.

## Python packages

Exact resolved versions are recorded in `uv.lock`. The direct runtime dependency
is `huggingface-hub`; `pytest` and `ruff` are development dependencies. Their
licenses remain with their respective projects.

## Research papers and systems

FreeToken, MawForge, SliceMoE, NPUMoE, FusionML, BaseRT, ZipMoE, MemSpec,
EcoSpec, SpecOffload, and the kernel-managed expert-cache work are cited as prior
art in `PRIOR_ART.md` and `paper/references.bib`. They are not software
dependencies unless explicitly added in a future baseline manifest.

FreeToken is a research and onboarding reference only; no FreeToken code is
copied into ElasticUMA.
