from __future__ import annotations

import fcntl
import os
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path

from huggingface_hub import HfApi, snapshot_download
from huggingface_hub.errors import LocalEntryNotFoundError

from .schema import ModelPlan
from .util import atomic_write_json, gib, utc_now

DEFAULT_RESERVE_GIB = 100
DEFAULT_MAX_MODEL_GIB = 80
DEFAULT_STORE_LIMIT_GIB = 120


def cache_root() -> Path:
    configured = os.environ.get("ELASTICUMA_CACHE_ROOT")
    return (
        Path(configured).expanduser() if configured else Path.home() / "Library/Caches/elasticuma"
    )


def hf_cache_root() -> Path:
    return cache_root() / "huggingface" / "hub"


def project_manifest_root(project_root: Path) -> Path:
    return project_root / ".models"


def _repo_slug(repo_id: str) -> str:
    return f"models--{repo_id.replace('/', '--')}"


def _candidate_hf_roots() -> tuple[Path, ...]:
    candidates = [
        hf_cache_root(),
        Path.home() / ".cache/huggingface/hub",
        Path.home() / "Library/Caches/huggingface/hub",
    ]
    if value := os.environ.get("HF_HUB_CACHE"):
        candidates.append(Path(value).expanduser())
    unique: list[Path] = []
    for candidate in candidates:
        resolved = candidate.resolve(strict=False)
        if resolved not in unique:
            unique.append(resolved)
    return tuple(unique)


def _snapshot_if_complete(root: Path, repo_id: str, revision: str) -> Path | None:
    try:
        path = snapshot_download(
            repo_id=repo_id,
            revision=revision,
            cache_dir=root,
            local_files_only=True,
        )
    except (FileNotFoundError, LocalEntryNotFoundError, ValueError, OSError):
        return None
    snapshot = Path(path)
    if not (snapshot / "config.json").is_file():
        return None
    if not any(snapshot.glob("*.safetensors")) and not any(snapshot.glob("*.gguf")):
        return None
    return snapshot


def find_existing_snapshot(repo_id: str, revision: str) -> tuple[Path, Path] | None:
    for root in _candidate_hf_roots():
        if snapshot := _snapshot_if_complete(root, repo_id, revision):
            return snapshot, root
    return None


def _physical_store_bytes(root: Path) -> int:
    total = 0
    if not root.exists():
        return 0
    for path in root.rglob("*"):
        try:
            if path.is_file() and not path.is_symlink():
                total += path.stat().st_size
        except FileNotFoundError:
            continue
    return total


def _env_gib(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    parsed = int(value)
    if parsed <= 0:
        raise ValueError(f"{name} must be positive")
    return parsed


def preflight(repo_id: str, revision: str) -> ModelPlan:
    if not revision or revision in {"latest", "HEAD"}:
        raise ValueError("an explicit branch, tag, or commit is required")
    info = HfApi().model_info(repo_id, revision=revision, files_metadata=True)
    resolved = str(info.sha)
    published = sum(int(item.size or 0) for item in info.siblings or [])
    root = hf_cache_root()
    root.mkdir(parents=True, exist_ok=True)
    existing = find_existing_snapshot(repo_id, resolved)
    reserve = _env_gib("ELASTICUMA_DISK_RESERVE_GIB", DEFAULT_RESERVE_GIB) * 1024**3
    max_model = _env_gib("ELASTICUMA_MAX_MODEL_GIB", DEFAULT_MAX_MODEL_GIB) * 1024**3
    store_limit = _env_gib("ELASTICUMA_STORE_LIMIT_GIB", DEFAULT_STORE_LIMIT_GIB) * 1024**3
    free = shutil.disk_usage(root).free
    store_bytes = _physical_store_bytes(cache_root())
    reasons: list[str] = []
    if existing:
        action = "reuse"
    else:
        action = "download"
        if published <= 0:
            reasons.append("the Hub did not report a positive model size")
        if published > max_model:
            reasons.append(
                f"published model size {gib(published):.1f} GiB exceeds the "
                f"single-model limit {gib(max_model):.1f} GiB"
            )
        if free - published < reserve:
            reasons.append(
                f"download would leave {gib(free - published):.1f} GiB, below the "
                f"{gib(reserve):.1f} GiB reserve"
            )
        if store_bytes + published > store_limit:
            reasons.append(f"canonical model store would exceed {gib(store_limit):.1f} GiB")
        if reasons:
            action = "refuse"
    return ModelPlan(
        repo_id=repo_id,
        requested_revision=revision,
        resolved_revision=resolved,
        published_bytes=published,
        cache_root=root,
        existing_snapshot=existing[0] if existing else None,
        existing_cache_root=existing[1] if existing else None,
        disk_free_bytes=free,
        disk_reserve_bytes=reserve,
        store_physical_bytes=store_bytes,
        store_limit_bytes=store_limit,
        action=action,
        reasons=tuple(reasons),
    )


@contextmanager
def download_lock() -> Iterator[None]:
    root = cache_root()
    root.mkdir(parents=True, exist_ok=True)
    path = root / "download.lock"
    with path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def fetch(project_root: Path, repo_id: str, revision: str) -> tuple[ModelPlan, Path]:
    with download_lock():
        plan = preflight(repo_id, revision)
        if plan.action == "refuse":
            raise RuntimeError("model download refused: " + "; ".join(plan.reasons))
        if plan.existing_snapshot:
            snapshot = plan.existing_snapshot
        else:
            snapshot = Path(
                snapshot_download(
                    repo_id=repo_id,
                    revision=plan.resolved_revision,
                    cache_dir=plan.cache_root,
                    local_dir=None,
                    max_workers=4,
                )
            )
        manifest = {
            "schema_version": 1,
            "registered_at": utc_now(),
            "repo_id": repo_id,
            "requested_revision": revision,
            "resolved_revision": plan.resolved_revision,
            "published_bytes": plan.published_bytes,
            "snapshot_path": str(snapshot),
            "cache_root": str(plan.existing_cache_root or plan.cache_root),
            "download_action": plan.action,
            "preflight": asdict(plan),
        }
        name = f"{_repo_slug(repo_id)}--{plan.resolved_revision}.json"
        atomic_write_json(project_manifest_root(project_root) / name, manifest)
        return plan, snapshot


def list_registered(project_root: Path) -> list[dict[str, object]]:
    root = project_manifest_root(project_root)
    if not root.exists():
        return []
    import json

    rows: list[dict[str, object]] = []
    for path in sorted(root.glob("*.json")):
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        payload["manifest_path"] = str(path)
        payload["snapshot_exists"] = Path(str(payload.get("snapshot_path", ""))).is_dir()
        rows.append(payload)
    return rows


def resolve_registered(project_root: Path, repo_id: str, revision: str) -> Path:
    matches = [
        row
        for row in list_registered(project_root)
        if row.get("repo_id") == repo_id
        and revision in {row.get("requested_revision"), row.get("resolved_revision")}
        and row.get("snapshot_exists") is True
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"expected one registered snapshot for {repo_id}@{revision}, found {len(matches)}; "
            "run `elasticuma model preflight` and `elasticuma model fetch` once"
        )
    return Path(str(matches[0]["snapshot_path"]))
