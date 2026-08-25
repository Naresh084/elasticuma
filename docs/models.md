# Models and architecture support

ElasticUMA uses three simple support labels:

- **Verified** — we ran the exact checkpoint through controlled correctness and
  performance tests.
- **Runtime-compatible** — the native runtime recognizes the architecture and a
  completed `.gturbo` model passes its integrity checks, but this exact
  checkpoint has not completed ElasticUMA's evaluation.
- **Not implemented** — the tokenizer, tensor layout, routing, quantization, or
  Metal kernels are missing. A catalog entry cannot fix that.

## Supported today

| ID | Exact verified checkpoint | Native family | Shape | ElasticUMA inputs | Status |
|---|---|---|---|---|---|
| `qwen36` | `mlx-community/Qwen3.6-35B-A3B-4bit` | `qwen36` / `qwen3_5_moe` | 40 layers, 256 experts, 8 routed | Text | Verified on M1 Max / 32 GiB |
| `gemma4` | `mlx-community/gemma-4-26b-a4b-it-4bit` | `gemma4` | 30 layers, 128 experts, 8 routed | Text | Verified on M1 Max / 32 GiB |

Modalities are declared per model profile. They describe the complete
ElasticUMA path—installer, tokenizer, runtime, app, CLI, and server—not merely
what exists upstream. The current Qwen and Gemma installers intentionally drop
vision-tower tensors, so both profiles remain text-only until their vision paths
are implemented and validated.

List these from the installed CLI:

```bash
uv run euma models
```

Both a short id and the catalogued Hugging Face repository id resolve to the
same profile:

```bash
uv run euma setup qwen36
uv run euma setup mlx-community/Qwen3.6-35B-A3B-4bit
```

## Native architecture boundary

The pinned Swift/Metal runtime currently contains two model-family paths:

| Native path | What it implements | What it does not imply |
|---|---|---|
| Qwen 3.6 MoE | Qwen tokenizer/chat path, `qwen3_5_moe` tensor mapping, 4-bit expert packing, Qwen routing and recurrent/attention blocks, Qwen Metal kernels | Arbitrary Qwen size, Qwen3.8 Max, dense Qwen, or another `qwen3_5_moe` checkpoint is not automatically verified |
| Gemma 4 MoE | Gemma tokenizer/chat path, Gemma 4 A4B tensor mapping, 4-bit expert packing, Gemma routing/attention blocks, Gemma Metal kernels | Other Gemma sizes, dense Gemma, vision paths, or a different quantization are not automatically verified |

A verified `.gturbo` directory can be passed directly when it uses one of those
implemented families:

```bash
uv run euma serve /absolute/path/to/model.gturbo
```

## Recent and widely requested MoE models

Status checked on 25 August 2026. “Not implemented” means exactly that; it does
not mean the model is impossible forever.

| Model | Architecture / scale | ElasticUMA status | Main missing work |
|---|---|---|---|
| [Qwen3.6-35B-A3B](https://huggingface.co/Qwen/Qwen3.6-35B-A3B) | `qwen3_5_moe`, 35B total / 3B active | **Verified** through the pinned Q4 profile | Text generation is implemented; the upstream vision tower is deliberately not packed |
| [Gemma 4 26B-A4B](https://huggingface.co/google/gemma-4-26B-A4B-it) | Gemma 4 MoE, 26B total / about 4B active | **Verified** through the pinned Q4 profile | Text path works; other sizes and formats need validation |
| [Qwen3.5-35B-A3B](https://huggingface.co/Qwen/Qwen3.5-35B-A3B) | Qwen `qwen3_5_moe` family | **Not verified** | Exact config, tokenizer, packing, output parity, and kernels must pass; the similar family name is insufficient |
| [Qwen3.8-2.4T-A95B](https://huggingface.co/Qwen/Qwen3.8-2.4T-A95B) | `qwen3_5_moe_text`, 2.4T total / 95B active | **Not implemented** | New scale/config support; the active working set is itself far beyond a 32 GiB Mac |
| [DeepSeek-V4-Flash-0731](https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash-0731) | DeepSeek V4 MoE with speculative module | **Not implemented** | DeepSeek tensor/MLA/routing path, quantization, tokenizer, speculative head, and Metal kernels |
| [GLM-5.2](https://huggingface.co/zai-org/GLM-5.2) | `glm_moe_dsa`, 753B with sparse IndexShare attention | **Not implemented** | GLM tokenizer, DSA/MLA state, expert format, routing, and Metal kernels; full checkpoint is not a 32 GiB target |
| [Kimi K3](https://huggingface.co/moonshotai/Kimi-K3) | `kimi_linear`, 2.8T / 104B active, 896 experts | **Not implemented** | KDA, Attention Residuals, LatentMoE, MXFP4/MXFP8, multimodal path, and kernels |
| [Kimi K2.5](https://huggingface.co/moonshotai/Kimi-K2.5) | `kimi_k2`, 1T / 32B active, 384 experts | **Not implemented** | MLA, shared/routed experts, compressed-tensor format, tokenizer, vision path, and kernels |
| [MiniMax-M2.5](https://huggingface.co/MiniMaxAI/MiniMax-M2.5) | `minimax_m2`, large agentic MoE | **Not implemented** | Custom model code, expert packing, routing, tokenizer, attention state, and Metal kernels |
| [Mistral Small 4 119B-A6B](https://huggingface.co/mistralai/Mistral-Small-4-119B-2603) | `mistral4`, 128 experts / 4 active | **Not implemented** | Mistral tokenizer, MLA, shared expert, FP8/NVFP4 packing, multimodal path, and kernels |
| [gpt-oss-120b](https://huggingface.co/openai/gpt-oss-120b) | `gpt_oss`, 117B / 5.1B active, MXFP4 | **Not implemented** | Harmony format, MXFP4 kernels, router/expert mapping, tokenizer, and numerical validation |
| [Mixtral-8x7B](https://huggingface.co/mistralai/Mixtral-8x7B-v0.1) | Classic sparse MoE, 8 experts / 2 active | **Not implemented** | Mistral tokenizer, Mixtral mapping, quantization, and Metal kernels |

### Practical priority for Mac support

The most useful next backend is not automatically the model with the largest
headline parameter count. For a 32–64 GiB Mac, active parameters, common dense
weights, checkpoint format, and required context state matter more.

A sensible implementation order is:

1. another checkpoint that exactly matches the existing Qwen path;
2. `gpt-oss-120b` or Mistral Small 4, because their active working sets are much
   smaller than Kimi K3 or Qwen3.8 Max;
3. DeepSeek-V4-Flash after a reusable MLA/routing backend exists;
4. GLM-5.2, Kimi K3, and Qwen3.8 Max only on machines whose storage and active
   working set make them meaningful.

This is a roadmap, not a support claim.

## Why one generic MoE loader is unsafe

Two models can both say “MoE” and still disagree on all of these:

- how expert tensors are named, fused, sliced, and quantized;
- whether shared experts exist and when they run;
- router normalization, grouping, top-k selection, and scaling;
- attention, recurrent, speculative, vision, and long-context state;
- tokenizer, chat template, tool calls, and stop tokens; and
- the Metal kernels required to reproduce the model's numerical semantics.

## Adding support

For a checkpoint that truly matches an implemented family, add a pinned catalog
profile under `models/` and validate the exact output. A new family needs:

1. tokenizer and chat semantics;
2. checkpoint-to-`.gturbo` tensor mapping and quantization decoding;
3. router, shared-expert, attention/recurrent, and context semantics;
4. Metal kernels plus numerical fixtures; and
5. fixed-versus-OS-managed output parity and a repeatable Mac benchmark.

Set `input_modalities` in each catalog profile only after those modalities pass
end-to-end tests. A multimodal upstream repository is not itself a multimodal
ElasticUMA support claim.

Open a model-support issue with the official model link, exact revision,
architecture/config, desired quantization, and target Mac. Do not download a
second copy merely to test whether a name looks compatible.
