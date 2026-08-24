# Evidence data contract

All machine-readable evidence uses `schema_version = 1`. Paths below are local
run receipts and may be rewritten to relative paths only when producing a public
artifact bundle. Raw files are append-only.

## Raw run directory

```text
artifacts/raw/<experiment>/<run-id>/
  messages.json
  stdout.log
  stderr.log
  runtime-result.json
  record.json
```

`record.json` is the orchestration authority. `runtime-result.json` is the
adapter-specific runtime receipt. Logs are retained for audit but never parsed
during aggregate analysis after the adapter has produced a structured result.

## Required run fields

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | integer | Evidence schema version |
| `run_id` | string | Globally unique timestamp-plus-random identifier |
| `evidence_state` | enum | `raw`, `admitted`, `diagnostic`, `projected`, or `rejected` |
| `experiment_name`, `arm_name` | string | Preregistered experiment and fixed-policy arm |
| `schedule_index`, `repetition`, `warmup` | integer/integer/boolean | Exact balanced schedule position |
| `started_at`, `finished_at` | ISO-8601 string | UTC wall-clock bounds |
| `duration_seconds` | number | Monotonic elapsed time |
| `model_repo`, `model_revision`, `model_path` | string | Immutable model identity and resolved local artifact |
| `prompt_sha256`, `command_sha256` | 64-char hex string | Input and rendered-command identity |
| `cache_mib`, `pressure_mib` | integer | Declared expert cache and optional pressure budget |
| `return_code`, `timed_out`, `errors` | integer/null, boolean, string array | Failure surface; never inferred from missing data |
| `hardware` | object | Privacy-safe chip, core counts, memory, OS, architecture |
| `memory_before`, `memory_after` | memory snapshot | Endpoint telemetry |
| `memory_samples` | memory snapshot array | In-run telemetry at configured cadence |
| `process_samples` | process snapshot array | Root process-tree RSS, not unrelated commands |
| `power_before`, `power_after` | power snapshot | AC/battery source, percentage, charging, low-power mode, and safe warning flags |
| `native_pressure_monitor_sha256` | 64-char hex string/null | Exact native monitor binary identity |
| `native_pressure_events` | object array | Kernel-delivered memory-pressure transition receipts, beginning with a monitor start record |
| `runtime` | runtime result | Adapter-normalized inference metrics |

## Memory snapshot

Memory snapshots contain monotonic and UTC times; macOS free percentage and
pressure level; VM page size and selected free/active/inactive/speculative/wired/
compressor counters; page-ins/page-outs; and swap total/used/free bytes. A null
means the OS command did not expose a parseable value. Null is not zero.

## Runtime result

The normalized runtime schema can hold:

- prompt/completion counts, prefill/decode throughput, and TTFT;
- response and token-ID hashes;
- expert hit rate, miss/access counts, explicit cache slots, optional miss bytes,
  materialized bytes, and evictions;
- MTP drafted/accepted counts;
- the full adapter payload under `runtime_payload`.

Metrics unsupported by a runtime remain null. A field name containing `_bytes`
must never contain an event count. This distinction prevents a common error where
“10 misses” is treated as “10 bytes.”

## Admitted artifact

`artifacts/admitted/<experiment>.json` contains the serialized experiment spec,
one decision per raw run, measured/admitted counts, a `complete` Boolean, and
only the admitted non-warmup records. The decision list preserves rejection
reasons even though rejected rows are absent from `records`.

Aggregate analysis is allowed only when `complete` is true and at least one
record exists. Paper tables must point to this file and the analysis program.

## Evolution

Schema changes increment the top-level version and add a migration or a reader
that rejects unsupported versions. Do not reinterpret an existing field. Add a
new field with its unit encoded in the name.
