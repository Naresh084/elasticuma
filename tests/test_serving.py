from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import elasticuma.serving as serving
from elasticuma.catalog import resolve_profile
from elasticuma.runtime_store import packed_model_path
from elasticuma.serving import resolve_model, run_plan, serve_plan


def _verified_model(path: Path, model_id: str = "test-model") -> Path:
    path.mkdir(parents=True)
    (path / "manifest.json").write_text(json.dumps({"modelID": model_id}), encoding="utf-8")
    (path / "verified-install.json").write_text("{}", encoding="utf-8")
    (path / "model_weights.bin").write_bytes(b"weights")
    return path


def _runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "runtime"
    release = root / ".build/release"
    release.mkdir(parents=True)
    for name in ("slipstream", "slipstream-server"):
        binary = release / name
        binary.write_bytes(b"binary")
        binary.chmod(0o755)
    monkeypatch.setenv("ELASTICUMA_RUNTIME_ROOT", str(root))
    monkeypatch.setattr(serving, "runtime_status", lambda _project: {"ready": True})
    return root


def test_direct_verified_model_path_needs_no_catalog(tmp_path: Path) -> None:
    model = _verified_model(tmp_path / "custom.gturbo", "custom-compatible")
    resolved = resolve_model(tmp_path, str(model))
    assert resolved.path == model.resolve()
    assert resolved.model_id == "custom-compatible"
    assert resolved.profile is None


def test_serve_plan_uses_admitted_profile_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ELASTICUMA_CACHE_ROOT", str(tmp_path / "cache"))
    _runtime(tmp_path, monkeypatch)
    profile = resolve_profile("qwen36")
    _verified_model(packed_model_path(profile), profile.packed_model_id)

    plan = serve_plan(tmp_path, "qwen36")
    assert plan.mode == "serve"
    assert "--expert-cache-residency" in plan.command
    assert plan.command[plan.command.index("--expert-cache-residency") + 1] == "os-managed"
    assert plan.command[plan.command.index("--expert-cache-slots") + 1] == "96"
    assert plan.command[plan.command.index("--expert-cache-hot-slots") + 1] == "16"


def test_run_plan_rejects_impossible_hot_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _runtime(tmp_path, monkeypatch)
    model = _verified_model(tmp_path / "custom.gturbo")
    with pytest.raises(ValueError, match="hot slots"):
        run_plan(tmp_path, str(model), "hello", cache_slots=16, hot_slots=24)


def test_run_plan_uses_non_thinking_chat_prompt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _runtime(tmp_path, monkeypatch)
    model = _verified_model(tmp_path / "custom.gturbo")
    plan = run_plan(tmp_path, str(model), "hello")
    assert "--chat-prompt" in plan.command
    assert "--prompt" not in plan.command


def test_runtime_status_binds_binaries_to_bundled_and_staged_patch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    patch_root = project / "runtime/patches"
    source_root = Path(__file__).resolve().parents[1] / "runtime/patches"
    patch_root.mkdir(parents=True)
    for name in ("elasticuma-purgeable.patch", "elasticuma-app.patch"):
        (patch_root / name).write_bytes((source_root / name).read_bytes())
    runtime = tmp_path / "runtime"
    (runtime / ".git").mkdir(parents=True)
    release = runtime / ".build/release"
    release.mkdir(parents=True)
    for name in (
        "slipstream-repack",
        "slipstream",
        "slipstream-server",
        "slipstream-mac",
        "slipstream-decode-service",
    ):
        binary = release / name
        binary.write_bytes(b"binary")
        binary.chmod(0o755)
    monkeypatch.setenv("ELASTICUMA_RUNTIME_ROOT", str(runtime))

    def fake_run(command, **kwargs):
        del kwargs
        if "rev-parse" in command:
            return SimpleNamespace(returncode=0, stdout=f"{serving.UPSTREAM_RUNTIME_REVISION}\n")
        if "ls-files" in command:
            return SimpleNamespace(returncode=0, stdout="")
        if "--quiet" in command:
            return SimpleNamespace(returncode=0, stdout=b"")
        return SimpleNamespace(returncode=0, stdout=b"staged patch set")

    monkeypatch.setattr(serving.subprocess, "run", fake_run)

    class FakeDigest:
        def hexdigest(self):
            return serving.RUNTIME_PATCHSET_SHA256

    real_sha256 = serving.hashlib.sha256

    def fake_sha256(payload=b""):
        if payload == b"staged patch set":
            return FakeDigest()
        return real_sha256(payload)

    monkeypatch.setattr(serving.hashlib, "sha256", fake_sha256)
    status = serving.runtime_status(project)
    assert status["patch_valid"] is True
    assert status["patches"]["mechanism"]["valid"] is True
    assert status["patches"]["app"]["valid"] is True
    assert status["staged_patch_valid"] is True
    assert status["source_clean"] is True
    assert status["ready"] is True
