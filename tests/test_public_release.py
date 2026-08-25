from __future__ import annotations

import re
from pathlib import Path

from elasticuma.util import sha256_file

ROOT = Path(__file__).resolve().parents[1]


def test_public_runtime_patches_and_paper_are_pinned() -> None:
    assert sha256_file(ROOT / "runtime/patches/elasticuma-purgeable.patch") == (
        "433f38c094aca85701129bdaa9b1e3397a0a7f8f45759c4af2050f2f0bdfbde9"
    )
    assert sha256_file(ROOT / "runtime/patches/elasticuma-app.patch") == (
        "d02b916072148f6fe8c05ad8352a767f828e0eaea0c8ee010d16f52c1666e4de"
    )
    assert sha256_file(ROOT / "paper/ElasticUMA-paper.pdf") == (
        "3334189ace4bea20267fd84a1fd91a5c76bf67de3b45eea570e2ee5745beb3c0"
    )


def test_public_bootstrap_has_no_private_sibling_dependency() -> None:
    script = (ROOT / "scripts/bootstrap_candidate_runtime.sh").read_text(encoding="utf-8")
    assert "../elasticuma-runtime" not in script
    assert "ELASTICUMA_CANDIDATE_RUNTIME_REPO" not in script
    assert "runtime/patches/elasticuma-purgeable.patch" in script
    assert "runtime/patches/elasticuma-app.patch" in script


def test_relative_markdown_links_resolve() -> None:
    sources = [
        ROOT / "README.md",
        ROOT / "CHANGELOG.md",
        ROOT / "CONTRIBUTING.md",
        ROOT / "SECURITY.md",
        ROOT / "docs/cli.md",
        ROOT / "docs/app.md",
        ROOT / "docs/install.md",
        ROOT / "docs/models.md",
        ROOT / "docs/quickstart.md",
        ROOT / "docs/sdk.md",
        ROOT / "models/README.md",
        ROOT / "paper/README.md",
        ROOT / "paper/latex/README.md",
        ROOT / "runtime/README.md",
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


def test_readme_has_one_plain_paper_link_and_no_research_dump() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert readme.count("[Paper](paper/ElasticUMA-paper.pdf)") == 1
    assert "Paper (Word)" not in readme
    assert "artifacts/" not in readme
    assert "reports/" not in readme
