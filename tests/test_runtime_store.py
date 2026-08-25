from __future__ import annotations

import json
from pathlib import Path

import pytest

import elasticuma.runtime_store as runtime_store
from elasticuma.runtime_store import (
    GEMMA4_SPEC,
    QWEN36_SPEC,
    _register,
    packed_model_path,
    packed_preflight,
)
from elasticuma.util import sha256_file


def test_generic_packed_registration_accepts_each_pinned_model(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    release = runtime / ".build/release"
    release.mkdir(parents=True)
    (release / "slipstream").write_bytes(b"runtime")
    (release / "slipstream-repack").write_bytes(b"repacker")

    for spec in (QWEN36_SPEC, GEMMA4_SPEC):
        project = tmp_path / spec.selector / "project"
        model = tmp_path / spec.selector / "model.gturbo"
        model.mkdir(parents=True)
        manifest = {
            "magic": "GTURBO",
            "modelID": spec.packed_model_id,
            "sourceSnapshotHash": f"sha256:{spec.source_index_sha256}",
        }
        manifest_path = model / "manifest.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        (model / "model_weights.bin").write_bytes(b"weights")
        receipt = {
            "sourceRepoID": spec.repo_id,
            "sourceRevision": spec.revision,
            "manifestSha256": sha256_file(manifest_path),
            "modelDirectoryPath": str(model.resolve()),
            "toolVersion": "test",
        }
        (model / "verified-install.json").write_text(json.dumps(receipt), encoding="utf-8")

        registration = _register(project, runtime, model, spec)
        payload = json.loads(registration.read_text(encoding="utf-8"))
        assert payload["repo_id"] == spec.repo_id
        assert payload["resolved_revision"] == spec.revision
        assert payload["packed_model_id"] == spec.packed_model_id


def test_existing_verified_model_preflight_is_offline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ELASTICUMA_CACHE_ROOT", str(tmp_path / "cache"))
    runtime = tmp_path / "runtime"
    release = runtime / ".build/release"
    release.mkdir(parents=True)
    for name in ("slipstream", "slipstream-repack"):
        (release / name).write_bytes(b"binary")
    model = packed_model_path(QWEN36_SPEC)
    model.mkdir(parents=True)
    (model / "manifest.json").write_text("{}", encoding="utf-8")
    (model / "verified-install.json").write_text("{}", encoding="utf-8")
    (model / "model_weights.bin").write_bytes(b"weights")
    monkeypatch.setattr(
        runtime_store,
        "_runtime_head",
        lambda _root: runtime_store.SLIPSTREAM_REVISION,
    )
    monkeypatch.setattr(
        runtime_store,
        "_runtime_patch_sha256",
        lambda _root: runtime_store.ELASTICUMA_PATCH_SHA256,
    )
    monkeypatch.setattr(runtime_store, "find_existing_snapshot", lambda *_args: None)
    monkeypatch.setattr(
        runtime_store,
        "HfApi",
        lambda: (_ for _ in ()).throw(AssertionError("Hub must not be contacted")),
    )

    plan = packed_preflight(runtime, QWEN36_SPEC)
    assert plan["verified_existing"] is True
    assert plan["allowed"] is True
