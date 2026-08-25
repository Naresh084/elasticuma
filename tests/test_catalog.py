from __future__ import annotations

import json
from pathlib import Path

import pytest

from elasticuma.catalog import builtin_profiles, load_profiles, resolve_profile


def _community_catalog(path: Path, *, identifier: str = "example-moe") -> Path:
    payload = {
        "schema_version": 1,
        "models": [
            {
                "id": identifier,
                "aliases": ["example-alias"],
                "display_name": "Example MoE",
                "architecture": "example-compatible-moe",
                "repo_id": "community/example-moe",
                "revision": "a" * 40,
                "source_index_sha256": "b" * 64,
                "packed_model_id": "community/example-moe",
                "repack_selector": "example-moe",
                "path_prefix": "example-moe",
                "layers": 24,
                "total_experts": 64,
                "active_experts": 4,
                "default_cache_slots": 48,
                "default_hot_slots": 16,
                "minimum_ram_gib": 24,
                "input_modalities": ["text"],
                "verification": "community",
                "evidence": "Contributor validation required",
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_builtin_catalog_has_two_admitted_architectures() -> None:
    profiles = builtin_profiles()
    assert [profile.id for profile in profiles] == ["qwen36", "gemma4"]
    assert all(profile.verification == "admitted" for profile in profiles)
    assert all(profile.input_modalities == ("text",) for profile in profiles)
    assert resolve_profile("qwen3.6").id == "qwen36"
    assert resolve_profile("mlx-community/Qwen3.6-35B-A3B-4bit").id == "qwen36"


def test_custom_catalog_extends_without_code_changes(tmp_path: Path) -> None:
    catalog = _community_catalog(tmp_path / "community.json")
    profiles = load_profiles((catalog,))
    assert [profile.id for profile in profiles] == ["qwen36", "gemma4", "example-moe"]
    assert resolve_profile("example-alias", extra_catalogs=(catalog,)).id == "example-moe"


def test_catalog_rejects_conflicts_and_mutable_revisions(tmp_path: Path) -> None:
    conflict = _community_catalog(tmp_path / "conflict.json", identifier="qwen36")
    with pytest.raises(ValueError, match="conflicts"):
        load_profiles((conflict,))

    payload = json.loads(conflict.read_text(encoding="utf-8"))
    payload["models"][0]["id"] = "mutable-model"
    payload["models"][0]["aliases"] = []
    payload["models"][0]["revision"] = "main"
    conflict.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="immutable 40-character commit"):
        load_profiles((conflict,))


def test_catalog_rejects_unimplemented_modality_labels(tmp_path: Path) -> None:
    catalog = _community_catalog(tmp_path / "modalities.json")
    payload = json.loads(catalog.read_text(encoding="utf-8"))
    payload["models"][0]["input_modalities"] = ["text", "telepathy"]
    catalog.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="input_modalities"):
        load_profiles((catalog,))
