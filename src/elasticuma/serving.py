from __future__ import annotations

import hashlib
import json
import os
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from .catalog import ModelProfile, project_catalog_paths, resolve_profile
from .runtime_store import packed_model_path
from .util import sha256_file

ALLOWED_CACHE_SLOTS = (8, 16, 24, 32, 48, 64, 96, 128, 192, 256)
ALLOWED_CONTEXT_TOKENS = (4096, 8192, 16384, 32768, 65536)
MODEL_PROCESS_PATTERN = (
    "slipstream-server|slipstream-mac|slipstream-decode-service|"
    "TurboFieldfareServer|TurboFieldfareMac|TurboFieldfareDecodeService"
)
RUNTIME_PATCH_SHA256 = "9db7cbc8ce330068f292174e06834af43bf1607091a538d3dbad9f3eba4e1733"
UPSTREAM_RUNTIME_REVISION = "01f7d5e774ca940982ea3aa012bd880b5c9d634e"


@dataclass(frozen=True)
class ResolvedModel:
    path: Path
    model_id: str
    profile: ModelProfile | None


@dataclass(frozen=True)
class LaunchPlan:
    mode: str
    binary: Path
    model: ResolvedModel
    command: tuple[str, ...]
    environment: dict[str, str]

    def public_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "binary": str(self.binary),
            "binary_sha256": sha256_file(self.binary),
            "model": {
                "path": str(self.model.path),
                "model_id": self.model.model_id,
                "profile": self.model.profile.public_dict() if self.model.profile else None,
            },
            "command": list(self.command),
            "environment": self.environment,
        }


def runtime_root(project_root: Path) -> Path:
    configured = os.environ.get("ELASTICUMA_RUNTIME_ROOT")
    return Path(configured).expanduser() if configured else project_root / ".runtime/elasticuma"


def runtime_status(project_root: Path) -> dict[str, object]:
    root = runtime_root(project_root)
    release = root / ".build/release"
    binaries = {
        "repacker": release / "slipstream-repack",
        "cli": release / "slipstream",
        "server": release / "slipstream-server",
    }
    patch = project_root / "runtime/patches/elasticuma-purgeable.patch"
    patch_sha = sha256_file(patch) if patch.is_file() else None
    staged_patch_sha = None
    runtime_head = None
    source_clean = False
    if (root / ".git").is_dir():
        staged = subprocess.run(
            ["/usr/bin/git", "diff", "--cached", "--binary", "--no-ext-diff"],
            cwd=root,
            capture_output=True,
            check=False,
        )
        head = subprocess.run(
            ["/usr/bin/git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            check=False,
            text=True,
        )
        unstaged = subprocess.run(
            ["/usr/bin/git", "diff", "--quiet"],
            cwd=root,
            capture_output=True,
            check=False,
        )
        untracked = subprocess.run(
            ["/usr/bin/git", "ls-files", "--others", "--exclude-standard"],
            cwd=root,
            capture_output=True,
            check=False,
            text=True,
        )
        if staged.returncode == 0:
            staged_patch_sha = hashlib.sha256(staged.stdout).hexdigest()
        if head.returncode == 0:
            runtime_head = head.stdout.strip()
        source_clean = (
            runtime_head == UPSTREAM_RUNTIME_REVISION
            and unstaged.returncode == 0
            and untracked.returncode == 0
            and not untracked.stdout.strip()
        )
    binaries_ready = all(path.is_file() and os.access(path, os.X_OK) for path in binaries.values())
    return {
        "schema_version": 1,
        "runtime_root": str(root),
        "upstream_revision": UPSTREAM_RUNTIME_REVISION,
        "runtime_head": runtime_head,
        "source_clean": source_clean,
        "patch_path": str(patch),
        "patch_sha256": patch_sha,
        "patch_valid": patch_sha == RUNTIME_PATCH_SHA256,
        "staged_patch_sha256": staged_patch_sha,
        "staged_patch_valid": staged_patch_sha == RUNTIME_PATCH_SHA256,
        "binaries": {
            name: {"path": str(path), "ready": path.is_file() and os.access(path, os.X_OK)}
            for name, path in binaries.items()
        },
        "ready": (
            binaries_ready
            and patch_sha == RUNTIME_PATCH_SHA256
            and staged_patch_sha == RUNTIME_PATCH_SHA256
            and source_clean
        ),
    }


def install_runtime(project_root: Path) -> dict[str, object]:
    script = project_root / "scripts/bootstrap_candidate_runtime.sh"
    if not script.is_file():
        raise RuntimeError(
            "runtime installation is available from a source checkout; "
            "clone the ElasticUMA repository first"
        )
    subprocess.run([str(script)], cwd=project_root, check=True)
    status = runtime_status(project_root)
    if status["ready"] is not True:
        raise RuntimeError("runtime build completed without all required release binaries")
    return status


def _verified_model(path: Path) -> bool:
    return (
        path.is_dir()
        and (path / "manifest.json").is_file()
        and (path / "verified-install.json").is_file()
        and (path / "model_weights.bin").is_file()
    )


def _manifest_model_id(path: Path) -> str:
    with (path / "manifest.json").open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    model_id = payload.get("modelID")
    if not isinstance(model_id, str) or not model_id:
        raise RuntimeError(f"packed model manifest has no modelID: {path}")
    return model_id


def catalog_paths(project_root: Path, extra: Iterable[Path] = ()) -> tuple[Path, ...]:
    return (*project_catalog_paths(project_root), *extra)


def resolve_model(
    project_root: Path,
    reference: str,
    *,
    extra_catalogs: Iterable[Path] = (),
) -> ResolvedModel:
    candidate = Path(reference).expanduser()
    if candidate.exists():
        resolved = candidate.resolve()
        if not _verified_model(resolved):
            raise RuntimeError(
                f"model path is not a completed verified .gturbo directory: {resolved}"
            )
        return ResolvedModel(path=resolved, model_id=_manifest_model_id(resolved), profile=None)

    catalogs = catalog_paths(project_root, extra_catalogs)
    profile = resolve_profile(reference, extra_catalogs=catalogs)
    path = packed_model_path(profile)
    if not _verified_model(path):
        raise RuntimeError(
            f"model {profile.id!r} is not installed at {path}; run "
            f"`elasticuma model preflight --profile {profile.id}` then "
            f"`elasticuma model install --profile {profile.id}`"
        )
    return ResolvedModel(path=path, model_id=profile.id, profile=profile)


def running_model_processes() -> tuple[str, ...]:
    completed = subprocess.run(
        ["/usr/bin/pgrep", "-fl", MODEL_PROCESS_PATTERN],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode not in {0, 1}:
        raise RuntimeError(f"pgrep failed with exit code {completed.returncode}")
    return tuple(line for line in completed.stdout.splitlines() if line.strip())


def _validate_cache(cache_slots: int, hot_slots: int) -> None:
    if cache_slots not in ALLOWED_CACHE_SLOTS:
        raise ValueError(f"cache slots must be one of {ALLOWED_CACHE_SLOTS}")
    if not 0 <= hot_slots <= cache_slots:
        raise ValueError("hot slots must be between zero and cache slots")


def serve_plan(
    project_root: Path,
    reference: str,
    *,
    port: int = 8080,
    max_context: int = 16384,
    queue_limit: int = 4,
    cache_slots: int | None = None,
    hot_slots: int | None = None,
    residency: str = "os-managed",
    model_id: str | None = None,
    extra_catalogs: Iterable[Path] = (),
) -> LaunchPlan:
    if not 1 <= port <= 65535:
        raise ValueError("port must be between 1 and 65535")
    if max_context not in ALLOWED_CONTEXT_TOKENS:
        raise ValueError(f"context must be one of {ALLOWED_CONTEXT_TOKENS}")
    if queue_limit <= 0:
        raise ValueError("queue limit must be positive")
    if residency not in {"fixed", "os-managed"}:
        raise ValueError("residency must be fixed or os-managed")
    model = resolve_model(project_root, reference, extra_catalogs=extra_catalogs)
    slots = cache_slots or (model.profile.default_cache_slots if model.profile else 96)
    hot = (
        hot_slots
        if hot_slots is not None
        else (model.profile.default_hot_slots if model.profile else 16)
    )
    _validate_cache(slots, hot)
    status = runtime_status(project_root)
    binary = runtime_root(project_root) / ".build/release/slipstream-server"
    if status["ready"] is not True:
        raise RuntimeError(
            "ElasticUMA server is absent or failed provenance checks; "
            "run `elasticuma runtime install`"
        )
    served_id = model_id or model.model_id
    command = (
        str(binary),
        "--model",
        str(model.path),
        "--model-id",
        served_id,
        "--port",
        str(port),
        "--max-context",
        str(max_context),
        "--queue-limit",
        str(queue_limit),
        "--prompt-cache-mode",
        "single-prefix",
        "--expert-cache-slots",
        str(slots),
        "--expert-cache-residency",
        residency,
        "--expert-cache-hot-slots",
        str(hot),
    )
    environment = {"TURBO_FIELDFARE_PHASES": "1"}
    return LaunchPlan("serve", binary, model, command, environment)


def run_plan(
    project_root: Path,
    reference: str,
    prompt: str,
    *,
    max_new: int = 256,
    max_context: int = 4096,
    cache_slots: int | None = None,
    hot_slots: int | None = None,
    residency: str = "os-managed",
    seed: int | None = None,
    extra_catalogs: Iterable[Path] = (),
) -> LaunchPlan:
    if not prompt:
        raise ValueError("prompt must not be empty")
    if max_new <= 0:
        raise ValueError("max-new must be positive")
    if max_context <= 0:
        raise ValueError("max-context must be positive")
    if residency not in {"fixed", "os-managed"}:
        raise ValueError("residency must be fixed or os-managed")
    model = resolve_model(project_root, reference, extra_catalogs=extra_catalogs)
    slots = cache_slots or (model.profile.default_cache_slots if model.profile else 96)
    hot = (
        hot_slots
        if hot_slots is not None
        else (model.profile.default_hot_slots if model.profile else 16)
    )
    _validate_cache(slots, hot)
    status = runtime_status(project_root)
    binary = runtime_root(project_root) / ".build/release/slipstream"
    if status["ready"] is not True:
        raise RuntimeError(
            "ElasticUMA CLI is absent or failed provenance checks; run `elasticuma runtime install`"
        )
    command = [
        str(binary),
        "--model",
        str(model.path),
        "--prompt",
        prompt,
        "--max-new",
        str(max_new),
        "--max-context",
        str(max_context),
        "--expert-cache-slots",
        str(slots),
        "--expert-cache-residency",
        residency,
        "--expert-cache-hot-slots",
        str(hot),
        "--prefill-chunk",
        "auto",
    ]
    if seed is not None:
        if seed < 0:
            raise ValueError("seed must be non-negative")
        command.extend(("--seed", str(seed)))
    environment = {"TURBO_FIELDFARE_PHASES": "1"}
    return LaunchPlan("run", binary, model, tuple(command), environment)


def launch(plan: LaunchPlan) -> None:
    conflicts = running_model_processes()
    if conflicts:
        formatted = "\n".join(f"  {row}" for row in conflicts)
        raise RuntimeError(f"another model process is already running:\n{formatted}")
    environment = os.environ.copy()
    environment.update(plan.environment)
    os.execve(plan.binary, list(plan.command), environment)
