from __future__ import annotations

import sysconfig
from pathlib import Path

UPSTREAM_RUNTIME_REVISION = "01f7d5e774ca940982ea3aa012bd880b5c9d634e"
MECHANISM_PATCH_SHA256 = "433f38c094aca85701129bdaa9b1e3397a0a7f8f45759c4af2050f2f0bdfbde9"
APP_PATCH_SHA256 = "d02b916072148f6fe8c05ad8352a767f828e0eaea0c8ee010d16f52c1666e4de"
RUNTIME_PATCHSET_SHA256 = "a009e905b3483f9e894cc8627a58de1353437565b22f3e13107364c7acb4739b"


def runtime_asset_root(project_root: Path) -> Path:
    source_root = project_root.resolve()
    installed_root = (Path(sysconfig.get_path("data")) / "share" / "elasticuma").resolve()
    for candidate in (source_root, installed_root):
        if (candidate / "runtime/patches/elasticuma-purgeable.patch").is_file() and (
            candidate / "runtime/patches/elasticuma-app.patch"
        ).is_file():
            return candidate
    return source_root


def runtime_patch_paths(project_root: Path) -> dict[str, Path]:
    root = runtime_asset_root(project_root) / "runtime/patches"
    return {
        "mechanism": root / "elasticuma-purgeable.patch",
        "app": root / "elasticuma-app.patch",
    }


def runtime_bootstrap_path(project_root: Path) -> Path:
    return runtime_asset_root(project_root) / "scripts/bootstrap_candidate_runtime.sh"


def macos_info_plist_path(project_root: Path) -> Path:
    return runtime_asset_root(project_root) / "macos/Info.plist"
