from __future__ import annotations

import re
from pathlib import Path

from elasticuma.util import sha256_file

ROOT = Path(__file__).resolve().parents[1]


def test_public_runtime_patch_and_paper_are_pinned() -> None:
    assert sha256_file(ROOT / "runtime/patches/elasticuma-purgeable.patch") == (
        "9db7cbc8ce330068f292174e06834af43bf1607091a538d3dbad9f3eba4e1733"
    )
    assert sha256_file(ROOT / "paper/ElasticUMA-paper.pdf") == (
        "5ddfdca7fc5d12cef7b106bb3f93e237186f09a373a0c7303fedbf78f13d7a27"
    )


def test_public_bootstrap_has_no_private_sibling_dependency() -> None:
    script = (ROOT / "scripts/bootstrap_candidate_runtime.sh").read_text(encoding="utf-8")
    assert "../elasticuma-runtime" not in script
    assert "ELASTICUMA_CANDIDATE_RUNTIME_REPO" not in script
    assert "runtime/patches/elasticuma-purgeable.patch" in script


def test_relative_markdown_links_resolve() -> None:
    sources = [
        ROOT / "README.md",
        ROOT / "CHANGELOG.md",
        ROOT / "CONTRIBUTING.md",
        ROOT / "SECURITY.md",
        ROOT / "docs/cli.md",
        ROOT / "docs/install.md",
        ROOT / "docs/models.md",
        ROOT / "docs/quickstart.md",
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
