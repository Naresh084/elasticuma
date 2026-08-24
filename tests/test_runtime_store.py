from __future__ import annotations

import json
from pathlib import Path

from elasticuma.runtime_store import GEMMA4_SPEC, QWEN36_SPEC, _register
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
