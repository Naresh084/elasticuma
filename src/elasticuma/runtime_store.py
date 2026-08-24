from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from huggingface_hub import HfApi

from .catalog import ModelProfile, resolve_profile
from .model_store import (
    DEFAULT_RESERVE_GIB,
    DEFAULT_STORE_LIMIT_GIB,
    cache_root,
    download_lock,
    find_existing_snapshot,
    project_manifest_root,
)
from .util import atomic_write_json, gib, sha256_file, utc_now

SLIPSTREAM_REPO = "https://github.com/dwijenpatel/slipstream.git"
SLIPSTREAM_REVISION = "01f7d5e774ca940982ea3aa012bd880b5c9d634e"
ELASTICUMA_PATCH_SHA256 = "dc0418cb83988d1679796af1d707dbdb03db8473fcff9c45e6ec52daee8dc850"
PackedModelSpec = ModelProfile
QWEN36_SPEC = resolve_profile("qwen36")
GEMMA4_SPEC = resolve_profile("gemma4")
QWEN36_REPO = QWEN36_SPEC.repo_id
QWEN36_REVISION = QWEN36_SPEC.revision
QWEN36_SOURCE_INDEX_SHA256 = QWEN36_SPEC.source_index_sha256
GEMMA4_REPO = GEMMA4_SPEC.repo_id
GEMMA4_REVISION = GEMMA4_SPEC.revision
GEMMA4_SOURCE_INDEX_SHA256 = GEMMA4_SPEC.source_index_sha256


def _directory_bytes(root: Path) -> int:
    total = 0
    if not root.exists():
        return total
    for path in root.rglob("*"):
        try:
            if path.is_file() and not path.is_symlink():
                total += path.stat().st_size
        except FileNotFoundError:
            continue
    return total


def _env_gib(name: str, default: int) -> int:
    import os

    value = int(os.environ.get(name, default))
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def _runtime_head(runtime_root: Path) -> str:
    completed = subprocess.run(
        ["/usr/bin/git", "rev-parse", "HEAD"],
        cwd=runtime_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _runtime_patch_sha256(runtime_root: Path) -> str:
    completed = subprocess.run(
        ["/usr/bin/git", "diff", "--cached", "--binary", "--no-ext-diff"],
        cwd=runtime_root,
        check=True,
        capture_output=True,
    )
    return hashlib.sha256(completed.stdout).hexdigest()


def _verified_install(model_path: Path) -> bool:
    return (
        model_path.is_dir()
        and (model_path / "manifest.json").is_file()
        and (model_path / "verified-install.json").is_file()
        and (model_path / "model_weights.bin").is_file()
    )


def packed_qwen36_path() -> Path:
    return packed_model_path(QWEN36_SPEC)


def packed_gemma4_path() -> Path:
    return packed_model_path(GEMMA4_SPEC)


def packed_model_path(spec: PackedModelSpec) -> Path:
    return cache_root() / "packed" / f"{spec.path_prefix}-{spec.revision}.gturbo"


def packed_preflight(runtime_root: Path, spec: PackedModelSpec = QWEN36_SPEC) -> dict[str, object]:
    head = _runtime_head(runtime_root)
    reasons: list[str] = []
    if head != SLIPSTREAM_REVISION:
        reasons.append(f"runtime HEAD {head} differs from pin {SLIPSTREAM_REVISION}")
    runtime_patch_sha = _runtime_patch_sha256(runtime_root)
    if runtime_patch_sha != ELASTICUMA_PATCH_SHA256:
        reasons.append("runtime staged diff does not match the bundled ElasticUMA patch")
    repacker = runtime_root / ".build/release/slipstream-repack"
    cli = runtime_root / ".build/release/slipstream"
    if not repacker.is_file() or not cli.is_file():
        reasons.append("pinned release binaries are missing")
    model_path = packed_model_path(spec)
    existing = _verified_install(model_path)
    source_existing = find_existing_snapshot(spec.repo_id, spec.revision)
    if source_existing and not existing:
        reasons.append(
            "a complete source snapshot already exists in another Hugging Face cache; "
            "refusing a second full transfer until a local-source repack path is selected"
        )
    info = HfApi().model_info(spec.repo_id, revision=spec.revision, files_metadata=True)
    published = sum(int(item.size or 0) for item in info.siblings or [])
    packed_root = model_path.parent
    packed_root.mkdir(parents=True, exist_ok=True)
    disk = shutil.disk_usage(packed_root)
    reserve = _env_gib("ELASTICUMA_DISK_RESERVE_GIB", DEFAULT_RESERVE_GIB) * 1024**3
    store_limit = _env_gib("ELASTICUMA_STORE_LIMIT_GIB", DEFAULT_STORE_LIMIT_GIB) * 1024**3
    store_bytes = _directory_bytes(cache_root() / "packed")
    if not existing and disk.free - published < reserve:
        reasons.append(
            f"streaming repack would leave {gib(disk.free - published):.1f} GiB, "
            f"below the {gib(reserve):.1f} GiB reserve"
        )
    if not existing and store_bytes + published > store_limit:
        reasons.append("canonical packed-model store would exceed its configured limit")
    return {
        "schema_version": 1,
        "runtime_repo": SLIPSTREAM_REPO,
        "runtime_revision": SLIPSTREAM_REVISION,
        "runtime_head": head,
        "runtime_patch_sha256": runtime_patch_sha,
        "runtime_root": str(runtime_root),
        "repacker_path": str(repacker),
        "cli_path": str(cli),
        "model_selector": spec.selector,
        "source_repo": spec.repo_id,
        "source_revision": spec.revision,
        "source_published_bytes": published,
        "source_published_gib": gib(published),
        "source_snapshot_elsewhere": str(source_existing[0]) if source_existing else None,
        "model_path": str(model_path),
        "verified_existing": existing,
        "disk_free_bytes": disk.free,
        "disk_free_gib": gib(disk.free),
        "disk_reserve_bytes": reserve,
        "disk_reserve_gib": gib(reserve),
        "allowed": not reasons,
        "reasons": reasons,
    }


def _register(
    project_root: Path,
    runtime_root: Path,
    model_path: Path,
    spec: PackedModelSpec,
) -> Path:
    manifest_path = model_path / "manifest.json"
    receipt_path = model_path / "verified-install.json"
    with manifest_path.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    with receipt_path.open("r", encoding="utf-8") as handle:
        receipt = json.load(handle)
    source_repo = receipt.get("sourceRepoID")
    source_reference = receipt.get("sourceRevision")
    snapshot_hash = manifest.get("sourceSnapshotHash")
    expected_snapshot_hash = f"sha256:{spec.source_index_sha256}"
    if manifest.get("magic") != "GTURBO" or manifest.get("modelID") != spec.packed_model_id:
        raise RuntimeError("packed manifest magic or model ID does not match the pinned model")
    if snapshot_hash != expected_snapshot_hash:
        raise RuntimeError(f"packed source-index hash mismatch: {snapshot_hash}")
    if source_repo not in {None, spec.repo_id}:
        raise RuntimeError(f"packed manifest source repo mismatch: {source_repo}")
    # The upstream local verify command deliberately rewrites sourceRevision to
    # the source-index hash and sourceRepoID to null. Accept either that verified
    # form or the original remote-install commit receipt, while pinning both here.
    if source_reference not in {None, spec.revision, expected_snapshot_hash}:
        raise RuntimeError(f"packed receipt source reference mismatch: {source_reference}")
    if receipt.get("manifestSha256") != sha256_file(manifest_path):
        raise RuntimeError("verified receipt is not bound to the current manifest")
    if Path(str(receipt.get("modelDirectoryPath", ""))).resolve() != model_path.resolve():
        raise RuntimeError("verified receipt is bound to a different model directory")
    payload = {
        "schema_version": 1,
        "registered_at": utc_now(),
        "repo_id": spec.repo_id,
        "requested_revision": spec.revision,
        "resolved_revision": spec.revision,
        "snapshot_path": str(model_path),
        "cache_root": str(model_path.parent),
        "format": "gturbo-v1",
        "packed_bytes": _directory_bytes(model_path),
        "runtime_repo": SLIPSTREAM_REPO,
        "runtime_revision": SLIPSTREAM_REVISION,
        "runtime_patch_sha256": ELASTICUMA_PATCH_SHA256,
        "runtime_binary_sha256": sha256_file(runtime_root / ".build/release/slipstream"),
        "repacker_binary_sha256": sha256_file(runtime_root / ".build/release/slipstream-repack"),
        "manifest_sha256": sha256_file(manifest_path),
        "verified_install_sha256": sha256_file(receipt_path),
        "packed_model_id": manifest["modelID"],
        "source_index_sha256": spec.source_index_sha256,
        "receipt_source_repo": source_repo,
        "receipt_source_reference": source_reference,
        "receipt_tool_version": receipt.get("toolVersion"),
    }
    repo_slug = spec.repo_id.replace("/", "--")
    target = project_manifest_root(project_root) / f"models--{repo_slug}--{spec.revision}.json"
    atomic_write_json(target, payload)
    return target


def install_packed_model(
    project_root: Path,
    runtime_root: Path,
    spec: PackedModelSpec,
) -> dict[str, object]:
    # This lock is rooted in the canonical cache, so a second project or shell
    # cannot start another model transfer while this one is in progress.
    with download_lock():
        plan = packed_preflight(runtime_root, spec)
        if not plan["allowed"]:
            raise RuntimeError("packed install refused: " + "; ".join(plan["reasons"]))
        model_path = Path(str(plan["model_path"]))
        if not _verified_install(model_path):
            command = [
                str(plan["repacker_path"]),
                "--model",
                spec.repack_selector,
                "--output",
                str(model_path),
            ]
            if model_path.exists():
                command.append("--resume")
            subprocess.run(command, cwd=runtime_root, check=True)
        manifest = _register(project_root, runtime_root, model_path, spec)
        return {
            "plan": plan,
            "model_path": model_path,
            "registration_manifest": manifest,
        }


def install_packed_qwen36(project_root: Path, runtime_root: Path) -> dict[str, object]:
    return install_packed_model(project_root, runtime_root, QWEN36_SPEC)


def packed_gemma4_preflight(runtime_root: Path) -> dict[str, object]:
    return packed_preflight(runtime_root, GEMMA4_SPEC)


def install_packed_gemma4(project_root: Path, runtime_root: Path) -> dict[str, object]:
    return install_packed_model(project_root, runtime_root, GEMMA4_SPEC)
