# Contributing

Thanks for helping make local MoE inference on Apple Silicon easier and safer.

## Before opening an issue

- Search existing issues.
- Run `uv run euma doctor`.
- Include the Mac chip, RAM, macOS, Swift version, ElasticUMA commit, exact model
  id, and the smallest command that reproduces the problem.
- Remove serial numbers, UUIDs, credentials, private prompts, and unrelated
  process details. Never upload model weights.

## Pull requests

1. Keep one user-visible change, bug fix, or model boundary per PR.
2. Add a focused test.
3. Run `make check`.
4. Update the short public documentation when behavior changes.
5. Report failures and regressions instead of selecting only successful runs.

## Model support

Read [the architecture matrix](docs/models.md) first.

- A profile change is appropriate only when the native family already matches.
- A new family needs tokenizer, checkpoint mapping, routing/attention semantics,
  Metal kernels, and numerical tests.
- Do not present a similar model name as compatibility evidence.

Open a model request with an official checkpoint URL, exact revision, config,
quantization, target Mac, and why the model is practical on that machine.

## Performance changes

Use the same model bytes, prompt, output length, and runtime settings for the
base and proposed versions. Report all repetitions plus throughput, physical
footprint, compression/swap behavior, and output parity. Label unreviewed
numbers as preliminary.

## AI assistance

AI-assisted contributions are welcome, but a human contributor must understand,
test, and take responsibility for every change and citation.

Contributions are accepted under Apache-2.0 and must preserve upstream notices.
