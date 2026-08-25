# Changelog

## 0.3.0 — 2026-08-25

- Replaces the experiment-led README with a plain-language problem, result,
  setup, and model-support guide.
- Adds `euma setup MODEL`, `euma models`, and short positional `run`/`serve`
  commands while keeping old flags compatible.
- Documents the exact native architecture boundary and current Qwen, DeepSeek,
  GLM, Kimi, MiniMax, Mistral, Gemma, and gpt-oss support status.
- Removes raw artifacts, generated reports, experiment grids, internal notes,
  and research-only helpers from the tracked end-user tree; local copies remain
  ignored and the evidence bundle is a separate release asset.

## 0.2.0 — 2026-08-25

First public research release.

- Reconstructs the exact native runtime from pinned upstream plus a verified
  Apache-2.0 patch.
- Adds reload-correct OS-managed expert residency with public CLI/server flags.
- Adds `elasticuma run`, `elasticuma serve`, runtime management, and a
  data-driven model catalog.
- Includes admitted Qwen3.6 and Gemma 4 profiles and direct verified `.gturbo`
  path serving.
- Includes the publication-quality paper and LaTeX source.
- Adds public install, quick-start, model-extension, CLI, contribution,
  security, and issue-template documentation.

Known scope: macOS 26+, Apple Silicon, one model worker, text generation, and
the two admitted MoE architectures. Cross-chip, energy, concurrency, and
independent reproduction remain open research work.
