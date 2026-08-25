from __future__ import annotations

import json

import elasticuma.cli as cli


def test_short_run_and_serve_syntax() -> None:
    parser = cli.build_parser()
    serve = parser.parse_args(["serve", "qwen36"])
    assert serve.model_ref == "qwen36"
    assert serve.model_option is None

    run = parser.parse_args(["run", "qwen36", "hello"])
    assert run.model_ref == "qwen36"
    assert run.prompt_text == "hello"


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
    monkeypatch.setattr(cli, "runtime_status", lambda _root: {"ready": False})
    assert cli.main(["setup", "qwen36", "--dry-run", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["runtime_action"] == "install"
    assert payload["model"]["id"] == "qwen36"
