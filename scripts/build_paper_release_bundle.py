#!/usr/bin/env python3
from __future__ import annotations

import gzip
import json
import os
import shutil
import tarfile
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from build_release_bundle import (
    copy_redacted,
    copy_tree_redacted,
    manifest_files,
    redact_text,
    replacements,
    safe_git_head,
    sha256_file,
)

PAPER_ARTIFACTS = {
    "gate1-m1max-qwen36-q4-v4.json": (
        30,
        "094d9f73549c332046fbfeb5459d2338c12ae5eb9494f473319a6a97b5910ab8",
    ),
    "purgeable-upstream-heldout-v6.json": (
        15,
        "5b23799f865385ceaf09aef5b4200d7c1da45e97170e01486e7bcaa641bfa0ad",
    ),
    "purgeable-upstream-nopressure-v7.json": (
        15,
        "06b78c1f2473256c7067dc05bf63c974d863bec22edf2cda9dc0b36e4527fa8e",
    ),
    "gemma4-purgeable-nopressure-v8.json": (
        15,
        "2b1c312e5660539c350082ca70ef65e8a93c6ee958ef947e8478598a4cba0a9e",
    ),
}

SUPPORTING_ADMITTED = (
    "io-path-gate-v1.json",
    "io-path-gate-v2.json",
    "io-path-gate-v3.json",
    "purgeable-allocation-gate-v1.json",
    "purgeable-layerwise-heldout-v5.json",
    "purgeable-layerwise-pressure-v4.json",
    "purgeable-pressure-probe-v1.json",
    "purgeable-selective-heldout-v3.json",
    "purgeable-selective-pressure-v2.json",
)

RAW_EXPERIMENTS = (
    "gate1-m1max-qwen36-q4-v4",
    "io-path-gate-v1",
    "io-path-gate-v2",
    "io-path-gate-v3",
    "purgeable-allocation-gate-v1",
    "purgeable-layerwise-heldout-v5",
    "purgeable-layerwise-pressure-v4",
    "purgeable-pressure-probe-v1",
    "purgeable-selective-heldout-v3",
    "purgeable-selective-pressure-v2",
    "purgeable-upstream-heldout-v6",
    "purgeable-upstream-nopressure-v7",
    "gemma4-purgeable-nopressure-v8",
    "qwen38-27b-mlx-dense-control-v1",
)

ANALYSES = (
    "gate1-m1max-qwen36-q4-v4-analysis.json",
    "gate1-m1max-qwen36-q4-v4-gate1.md",
    "gate1-m1max-qwen36-q4-v4-summary.csv",
    "purgeable-upstream-heldout-v6-purgeable-analysis.json",
    "purgeable-upstream-nopressure-v7-purgeable-analysis.json",
    "gemma4-purgeable-nopressure-v8-purgeable-analysis.json",
)

PAPER_FILES = (
    "ElasticUMA-paper.pdf",
)

PAPER_FIGURES = (
    "gate1-v4.svg",
    "elasticuma-architecture.html",
    "elasticuma-architecture.png",
    "elasticuma-main-results.png",
    "elasticuma-main-results.svg",
    "elasticuma-paired-gains.png",
    "elasticuma-paired-gains.svg",
    "elasticuma-cross-model.png",
    "elasticuma-cross-model.svg",
)

UPSTREAM_RUNTIME_COMMIT = "01f7d5e774ca940982ea3aa012bd880b5c9d634e"
CANDIDATE_RUNTIME_COMMIT = "ec84269d5ce162a0376099d39b30dd19aa99f096"
FIXED_MTIME = int(datetime(2026, 8, 24, 12, 0, tzinfo=UTC).timestamp())


def parse_args():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def copy_text_tree(source: Path, target: Path, pairs: list[tuple[str, str]]) -> None:
    ignored_parts = {".build", "__pycache__", ".pytest_cache", ".ruff_cache"}
    for path in sorted(source.rglob("*")):
        if path.is_dir() or ignored_parts.intersection(path.parts):
            continue
        destination = target / path.relative_to(source)
        copy_redacted(path, destination, pairs)
        destination.chmod(path.stat().st_mode & 0o777)


def copy_binary_checked(source: Path, target: Path, pairs: list[tuple[str, str]]) -> None:
    payload = source.read_bytes()
    for local_value, _ in pairs:
        if local_value.encode() in payload:
            raise RuntimeError(f"binary artifact contains a local path: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)


def validate_core_artifacts(project_root: Path) -> list[dict[str, object]]:
    rows = []
    admitted_root = project_root / "artifacts/admitted"
    for name, (expected_rows, expected_hash) in PAPER_ARTIFACTS.items():
        path = admitted_root / name
        if sha256_file(path) != expected_hash:
            raise RuntimeError(f"canonical artifact hash changed: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("complete") is not True or payload.get("admitted_count") != expected_rows:
            raise RuntimeError(f"canonical artifact is incomplete: {path}")
        rows.append(
            {
                "file": name,
                "measured_rows": expected_rows,
                "sha256": expected_hash,
            }
        )
    return rows


def create_runtime_patch(
    project_root: Path,
    staging: Path,
    pairs: list[tuple[str, str]],
) -> dict[str, str]:
    source_patch = project_root / "runtime/patches/elasticuma-purgeable.patch"
    source_documentation = project_root / "runtime/docs/ELASTICUMA_PURGEABLE_CACHE.md"
    expected_patch_sha = "dc0418cb83988d1679796af1d707dbdb03db8473fcff9c45e6ec52daee8dc850"
    if sha256_file(source_patch) != expected_patch_sha:
        raise RuntimeError("bundled runtime patch hash changed")
    patch_path = staging / "runtime/elasticuma-purgeable.patch"
    copy_redacted(source_patch, patch_path, pairs)
    copy_redacted(source_documentation, staging / "runtime/ELASTICUMA_PURGEABLE_CACHE.md", pairs)
    return {
        "upstream_commit": UPSTREAM_RUNTIME_COMMIT,
        "candidate_code_commit": CANDIDATE_RUNTIME_COMMIT,
        "patch_includes_public_documentation_updates": True,
        "patch_sha256": sha256_file(patch_path),
    }


def write_deterministic_archive(source: Path, archive: Path) -> None:
    with (
        archive.open("wb") as raw_handle,
        gzip.GzipFile(fileobj=raw_handle, mode="wb", filename="", mtime=0) as gzip_handle,
        tarfile.open(fileobj=gzip_handle, mode="w", format=tarfile.PAX_FORMAT) as handle,
    ):
        paths = [source, *sorted(source.rglob("*"))]
        for path in paths:
            arcname = Path(source.name) / path.relative_to(source)
            info = handle.gettarinfo(str(path), arcname.as_posix())
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.mtime = FIXED_MTIME
            if path.is_file():
                with path.open("rb") as file_handle:
                    handle.addfile(info, file_handle)
            else:
                handle.addfile(info)


def main() -> int:
    args = parse_args()
    project_root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    archive = output.with_suffix(".tar.gz")
    if output.exists() or archive.exists():
        raise SystemExit(f"refusing to overwrite release output: {output} or {archive}")

    core_artifacts = validate_core_artifacts(project_root)
    pairs = replacements(project_root)
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".elasticuma-paper-release-", dir=output.parent))
    try:
        for name in RAW_EXPERIMENTS:
            source = project_root / "artifacts/raw" / name
            if not source.is_dir():
                raise RuntimeError(f"required raw experiment is missing: {source}")
            copy_tree_redacted(source, staging / "evidence/raw" / name, pairs)

        admitted_names = [*PAPER_ARTIFACTS, *SUPPORTING_ADMITTED]
        for name in admitted_names:
            copy_redacted(
                project_root / "artifacts/admitted" / name,
                staging / "evidence/admitted" / name,
                pairs,
            )
        for name in ANALYSES:
            copy_redacted(
                project_root / "artifacts/figures" / name,
                staging / "evidence/analysis" / name,
                pairs,
            )
        for path in sorted((project_root / ".models").glob("*.json")):
            copy_redacted(path, staging / "provenance/models" / path.name, pairs)

        for directory in ("configs", "docs", "examples", "models", "scripts", "src", "tests"):
            copy_text_tree(
                project_root / directory,
                staging / "reproduction" / directory,
                pairs,
            )
        copy_text_tree(
            project_root / "native/Sources",
            staging / "reproduction/native/Sources",
            pairs,
        )
        for name in (
            "README.md",
            "CITATION.cff",
            "CHANGELOG.md",
            "CONTRIBUTING.md",
            "LICENSE",
            "Makefile",
            "NOTICE",
            "SECURITY.md",
            "pyproject.toml",
            "uv.lock",
        ):
            copy_redacted(project_root / name, staging / "reproduction" / name, pairs)

        copy_redacted(project_root / "paper/paper.md", staging / "paper/paper.md", pairs)
        for name in PAPER_FILES:
            copy_binary_checked(
                project_root / "paper" / name,
                staging / "paper" / name,
                pairs,
            )
        for name in PAPER_FIGURES:
            source = project_root / "paper/figures" / name
            destination = staging / "paper/figures" / name
            if source.suffix in {".pdf", ".png"}:
                copy_binary_checked(source, destination, pairs)
            else:
                copy_redacted(source, destination, pairs)

        runtime = create_runtime_patch(project_root, staging, pairs)
        metadata = {
            "schema_version": 1,
            "title": "ElasticUMA paper evidence bundle v1",
            "author": "Naresh Prajapati",
            "source_git_commit": safe_git_head(project_root),
            "runtime": runtime,
            "core_admitted_artifacts": core_artifacts,
            "core_measured_rows": sum(int(row["measured_rows"]) for row in core_artifacts),
            "model_weights_included": False,
            "runtime_build_products_included": False,
            "local_paths_redacted": True,
            "claim_scope": "two MoE architectures on one M1 Max",
            "open_claims": [
                "cross-generation Apple Silicon reproduction",
                "energy measurement",
                "independent reproduction",
                "long-context and concurrent desktop workloads",
            ],
            "notes": [
                "Qwen3.8 dense measurements are diagnostic and not admitted.",
                "Cumulative recovered bytes are reload traffic, not physical footprint.",
                "Paths use PROJECT_ROOT, MODEL_STORE, and USER_HOME placeholders.",
            ],
        }
        (staging / "bundle-metadata.json").write_text(
            json.dumps(metadata, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        readme = """# ElasticUMA paper evidence bundle v1

This bundle supports the scoped claim in *ElasticUMA: Reload-Correct OS-Managed
Expert Caching for Apple Silicon*. It includes redacted raw receipts, immutable
admitted JSON, derived analyses, paper figures, reproduction code, pinned model
manifests, and the exact native-runtime patch. It excludes model weights,
runtime build products, secrets, serial numbers, UUIDs, and machine-local paths.

Verify the bundle from this directory with:

```sh
shasum -a 256 -c SHA256SUMS
```

The core evidence contains 75 measured rows: 30 for the rejected Gate-1 cache
sweep and 15 each for Qwen pressure, Qwen no-pressure, and Gemma no-pressure.
The positive claim covers two MoE architectures on one M1 Max. It does not claim
all Apple hardware, energy superiority, or independent reproduction.

To reconstruct the native change, check out slipstream at the upstream commit
in `bundle-metadata.json`, apply `runtime/elasticuma-purgeable.patch`, and build
the release products. The reproduction configs remain safety-gated and must be
given new experiment names rather than appended to canonical raw directories.
"""
        (staging / "README.md").write_text(readme, encoding="utf-8")

        rows = manifest_files(staging)
        sums = "".join(f"{row['sha256']}  {row['path']}\n" for row in rows)
        (staging / "SHA256SUMS").write_text(sums, encoding="utf-8")

        for path in staging.rglob("*"):
            if path.is_file() and path.suffix not in {".pdf", ".png"}:
                redact_text(path.read_text(encoding="utf-8"), pairs)
        os.replace(staging, output)
        write_deterministic_archive(output, archive)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    print(json.dumps({"directory": str(output), "archive": str(archive)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
