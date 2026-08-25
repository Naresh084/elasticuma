from __future__ import annotations

import json
import re
import tarfile
from pathlib import Path

from elasticuma.util import sha256_file

ROOT = Path(__file__).resolve().parents[1]


def test_public_runtime_patch_and_paper_are_pinned() -> None:
    assert sha256_file(ROOT / "runtime/patches/elasticuma-purgeable.patch") == (
        "dc0418cb83988d1679796af1d707dbdb03db8473fcff9c45e6ec52daee8dc850"
    )
    assert sha256_file(ROOT / "paper/ElasticUMA-paper.pdf") == (
        "c3929e00a39d99a83d567c05514a59516149c3e2a0ffd820bb972e19b4d66d5b"
    )


def test_evidence_archive_contains_no_model_weight_file() -> None:
    archive = ROOT / "artifacts/releases/elasticuma-paper-v1.tar.gz"
    forbidden_suffixes = (".safetensors", ".gturbo", ".bin", ".pyc")
    with tarfile.open(archive, "r:gz") as handle:
        names = handle.getnames()
        assert "elasticuma-paper-v1/bundle-metadata.json" in names
        assert not any(name.endswith(forbidden_suffixes) for name in names)
        metadata_file = handle.extractfile("elasticuma-paper-v1/bundle-metadata.json")
        assert metadata_file is not None
        metadata = json.load(metadata_file)
    assert metadata["core_measured_rows"] == 75
    assert metadata["model_weights_included"] is False
    assert metadata["local_paths_redacted"] is True


def _without_runtime_documentation(patch: str) -> str:
    sections = patch.split("diff --git ")
    return "diff --git ".join(
        section
        for section in sections
        if not section.startswith(
            "a/docs/ELASTICUMA_PURGEABLE_CACHE.md b/docs/ELASTICUMA_PURGEABLE_CACHE.md"
        )
    )


def test_public_patch_changes_only_documentation_from_evidence_patch() -> None:
    archive = ROOT / "artifacts/releases/elasticuma-paper-v1.tar.gz"
    with tarfile.open(archive, "r:gz") as handle:
        archived_file = handle.extractfile("elasticuma-paper-v1/runtime/elasticuma-purgeable.patch")
        assert archived_file is not None
        archived_patch = archived_file.read().decode()
    public_patch = (ROOT / "runtime/patches/elasticuma-purgeable.patch").read_text()
    assert _without_runtime_documentation(public_patch) == _without_runtime_documentation(
        archived_patch
    )


def test_public_bootstrap_has_no_private_sibling_dependency() -> None:
    script = (ROOT / "scripts/bootstrap_candidate_runtime.sh").read_text(encoding="utf-8")
    assert "../elasticuma-runtime" not in script
    assert "ELASTICUMA_CANDIDATE_RUNTIME_REPO" not in script
    assert "runtime/patches/elasticuma-purgeable.patch" in script


def test_relative_markdown_links_resolve() -> None:
    sources = [
        *ROOT.glob("*.md"),
        *(ROOT / "docs").rglob("*.md"),
        *(ROOT / "models").rglob("*.md"),
        *(ROOT / "paper").glob("*.md"),
        *(ROOT / "runtime").rglob("*.md"),
    ]
    for source in sorted(set(sources)):
        text = source.read_text(encoding="utf-8")
        for target in re.findall(r"\[[^]]+\]\(([^)]+)\)", text):
            if "://" in target or target.startswith(("#", "mailto:")):
                continue
            path_text = target.split("#", 1)[0]
            if not path_text:
                continue
            assert (source.parent / path_text).exists(), f"broken link in {source}: {target}"
