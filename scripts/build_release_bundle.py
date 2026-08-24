#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path
from typing import Any

PROJECT_TOKEN = "${PROJECT_ROOT}"
MODEL_TOKEN = "${MODEL_STORE}"
HOME_TOKEN = "${USER_HOME}"
FORBIDDEN = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"serial\s*(?:number)?\s*[:=]",
        r"hardware\s+uuid\s*[:=]",
        r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----",
        r"\bhf_[A-Za-z0-9]{20,}\b",
    )
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def replacements(project_root: Path) -> list[tuple[str, str]]:
    model_root = Path.home() / "Library/Caches/elasticuma"
    return [
        (str(project_root), PROJECT_TOKEN),
        (str(model_root), MODEL_TOKEN),
        (str(Path.home()), HOME_TOKEN),
    ]


def redact_text(value: str, pairs: list[tuple[str, str]]) -> str:
    redacted = value
    for source, target in pairs:
        redacted = redacted.replace(source, target)
    for pattern in FORBIDDEN:
        if pattern.search(redacted):
            raise RuntimeError(f"forbidden sensitive pattern remains: {pattern.pattern}")
    return redacted


def copy_redacted(source: Path, target: Path, pairs: list[tuple[str, str]]) -> None:
    text = source.read_text(encoding="utf-8", errors="strict")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(redact_text(text, pairs), encoding="utf-8")


def copy_tree_redacted(source: Path, target: Path, pairs: list[tuple[str, str]]) -> None:
    for path in sorted(source.rglob("*")):
        if path.is_dir():
            continue
        copy_redacted(path, target / path.relative_to(source), pairs)


def safe_git_head(project_root: Path) -> str:
    return subprocess.run(
        ["/usr/bin/git", "rev-parse", "HEAD"],
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def manifest_files(root: Path) -> list[dict[str, Any]]:
    rows = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS":
            rows.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    return rows


def main() -> int:
    args = parse_args()
    project_root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    archive = output.with_suffix(".tar.gz")
    if output.exists() or archive.exists():
        raise SystemExit(f"refusing to overwrite release output: {output} or {archive}")
    admitted = project_root / "artifacts/admitted/gate1-m1max-qwen36-q4-v4.json"
    analysis = project_root / "artifacts/figures/gate1-m1max-qwen36-q4-v4-analysis.json"
    if not admitted.is_file() or not analysis.is_file():
        raise SystemExit("complete Gate-1 v4 admitted and analysis artifacts are required")
    admitted_payload = json.loads(admitted.read_text(encoding="utf-8"))
    if admitted_payload.get("complete") is not True or admitted_payload.get("admitted_count") != 30:
        raise SystemExit("Gate-1 v4 evidence is incomplete")

    pairs = replacements(project_root)
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".elasticuma-release-", dir=output.parent))
    try:
        raw_target = staging / "evidence/raw"
        for name in (
            "gate1-m1max-qwen36-q4",
            "gate1-m1max-qwen36-q4-v2",
            "gate1-m1max-qwen36-q4-v3",
            "gate1-m1max-qwen36-q4-v4",
        ):
            source = project_root / "artifacts/raw" / name
            if source.is_dir():
                copy_tree_redacted(source, raw_target / name, pairs)
        copy_redacted(admitted, staging / "evidence/admitted/gate1-v4.json", pairs)
        for name in (
            "gate1-m1max-qwen36-q4-v4-analysis.json",
            "gate1-m1max-qwen36-q4-v4-gate1.md",
            "gate1-m1max-qwen36-q4-v4-summary.csv",
        ):
            copy_redacted(
                project_root / "artifacts/figures" / name,
                staging / "evidence/analysis" / name,
                pairs,
            )
        for path in sorted((project_root / ".models").glob("*.json")):
            copy_redacted(path, staging / "provenance" / path.name, pairs)
        for name in (
            "gate1.example.toml",
            "gate1.v2.example.toml",
            "gate1.v3.example.toml",
            "gate1.v4.example.toml",
        ):
            copy_redacted(
                project_root / "configs" / name,
                staging / "protocols" / name,
                pairs,
            )
        copy_redacted(
            project_root / "configs/prompts/gate1-code.txt",
            staging / "protocols/gate1-code.txt",
            pairs,
        )
        copy_tree_redacted(
            project_root / "reports/gate1/evidence",
            staging / "evidence/public-tables",
            pairs,
        )
        copy_redacted(
            project_root / "reports/gate1/artifact.json",
            staging / "report/artifact.json",
            pairs,
        )
        copy_redacted(
            project_root / "reports/gate1/report.html",
            staging / "report/report.html",
            pairs,
        )
        copy_redacted(
            project_root / "paper/paper.md",
            staging / "paper/paper.md",
            pairs,
        )
        copy_redacted(
            project_root / "paper/figures/gate1-v4.svg",
            staging / "paper/figures/gate1-v4.svg",
            pairs,
        )
        metadata = {
            "schema_version": 1,
            "title": "ElasticUMA Gate-1 v4 evidence bundle",
            "source_git_commit": safe_git_head(project_root),
            "admitted_artifact_sha256": sha256_file(admitted),
            "analysis_artifact_sha256": sha256_file(analysis),
            "measured_rows": 30,
            "warmup_rows_v4": 6,
            "model_weights_included": False,
            "local_paths_redacted": True,
            "notes": [
                "V1-v3 failure receipts are included for auditability.",
                "Model weights and the external runtime checkout are excluded.",
                "Paths use PROJECT_ROOT, MODEL_STORE, and USER_HOME placeholders.",
            ],
        }
        (staging / "bundle-metadata.json").write_text(
            json.dumps(metadata, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        readme = """# ElasticUMA Gate-1 v4 evidence bundle

This bundle contains the redacted raw, admitted, and derived evidence supporting
the scoped Gate-1 result. It deliberately includes the v1-v3 stopped protocols
and receipts, excludes all model weights, and replaces machine-local paths with
placeholders. Verify every file with `shasum -a 256 -c SHA256SUMS`.

Reproduction code is identified by `source_git_commit` in
`bundle-metadata.json`. The paper result is `NOT PROVEN`: the paired median
16-to-96-slot slowdown was 10.54%, below the preregistered 15% threshold.
"""
        (staging / "README.md").write_text(readme, encoding="utf-8")
        rows = manifest_files(staging)
        sums = "".join(f"{row['sha256']}  {row['path']}\n" for row in rows)
        (staging / "SHA256SUMS").write_text(sums, encoding="utf-8")

        for path in staging.rglob("*"):
            if path.is_file():
                redact_text(path.read_text(encoding="utf-8"), pairs)
        os.replace(staging, output)
        with tarfile.open(archive, "w:gz", format=tarfile.PAX_FORMAT) as handle:
            handle.add(output, arcname=output.name)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    print(json.dumps({"directory": str(output), "archive": str(archive)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
