from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import elasticuma.cli as cli


def test_short_run_and_serve_syntax() -> None:
    parser = cli.build_parser()
    serve = parser.parse_args(["serve", "qwen36"])
    assert serve.model_ref == "qwen36"
    assert serve.model_option is None

    run = parser.parse_args(["run", "qwen36", "hello"])
    assert run.model_ref == "qwen36"
    assert run.prompt_text == "hello"
    assert run.diagnostics is False

    diagnostic = parser.parse_args(["run", "qwen36", "hello", "--diagnostics"])
    assert diagnostic.diagnostics is True


def test_native_app_commands_are_first_class() -> None:
    parser = cli.build_parser()
    build = parser.parse_args(["app", "build", "--configuration", "debug"])
    assert build.app_command == "build"
    assert build.configuration == "debug"
    opened = parser.parse_args(["app", "open", "--no-build"])
    assert opened.app_command == "open"
    assert opened.no_build is True


def test_public_help_hides_research_commands() -> None:
    help_text = cli.build_parser().format_help()
    assert "experiment" not in help_text
    assert "pressure" not in help_text


def test_legacy_model_and_prompt_flags_remain_compatible() -> None:
    args = cli.build_parser().parse_args(["run", "--model", "qwen36", "--prompt", "hello"])
    assert args.model_option == "qwen36"
    assert args.prompt_option == "hello"


def test_setup_dry_run_does_not_download(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(cli.ElasticUMA, "runtime_status", lambda _self: {"ready": False})
    assert cli.main(["setup", "qwen36", "--dry-run", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["runtime_action"] == "install"
    assert payload["model"]["id"] == "qwen36"


def test_app_build_uses_sdk_and_reports_path(monkeypatch, capsys, tmp_path: Path) -> None:
    app = tmp_path / "ElasticUMA.app"
    result = SimpleNamespace(path=app, as_dict=lambda: {"path": str(app)})
    monkeypatch.setattr(cli.ElasticUMA, "build_app", lambda _self, **_kwargs: result)
    assert cli.main(["app", "build"]) == 0
    assert str(app) in capsys.readouterr().out
