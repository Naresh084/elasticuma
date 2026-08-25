from __future__ import annotations

import socket
from pathlib import Path

import pytest

import elasticuma.sdk as sdk
from elasticuma import DownloadConfirmationRequired, ElasticUMA
from elasticuma.serving import LaunchPlan, ResolvedModel


def _verified_model(path: Path) -> None:
    path.mkdir(parents=True)
    (path / "manifest.json").write_text('{"modelID":"test"}', encoding="utf-8")
    (path / "verified-install.json").write_text("{}", encoding="utf-8")
    (path / "model_weights.bin").write_bytes(b"weights")


def test_public_sdk_lists_exact_support_and_install_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ELASTICUMA_CACHE_ROOT", str(tmp_path / "cache"))
    client = ElasticUMA(tmp_path / "project")
    before = client.model("qwen36")
    assert before.support == "verified"
    assert before.input_modalities == ("text",)
    assert before.installed is False
    _verified_model(before.model_path)
    after = client.model("qwen36")
    assert after.installed is True
    assert after.as_dict()["model_path"] == str(after.model_path)


def test_setup_plan_defers_model_network_checks_until_runtime_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = ElasticUMA(tmp_path)
    monkeypatch.setattr(sdk, "runtime_status", lambda _root: {"ready": False})

    def unexpected(*_args, **_kwargs):
        raise AssertionError("packed preflight must not run yet")

    monkeypatch.setattr(sdk, "packed_preflight", unexpected)
    plan = client.plan_setup("qwen36")
    assert plan.runtime_action == "install"
    assert plan.model_action == "preflight-after-runtime"
    assert plan.allowed is None


def test_sdk_requires_explicit_download_consent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ELASTICUMA_CACHE_ROOT", str(tmp_path / "cache"))
    client = ElasticUMA(tmp_path)
    monkeypatch.setattr(sdk, "runtime_status", lambda _root: {"ready": True})
    monkeypatch.setattr(sdk, "runtime_root", lambda _root: tmp_path / "runtime")
    monkeypatch.setattr(
        sdk,
        "packed_preflight",
        lambda *_args: {
            "verified_existing": False,
            "allowed": True,
            "reasons": [],
            "source_published_bytes": 10,
            "disk_free_bytes": 100,
            "disk_reserve_bytes": 20,
        },
    )
    monkeypatch.setattr(
        sdk,
        "install_packed_model",
        lambda *_args: (_ for _ in ()).throw(AssertionError("must not install")),
    )
    with pytest.raises(DownloadConfirmationRequired) as caught:
        client.setup("qwen36")
    assert caught.value.plan.needs_confirmation is True


def test_generate_captures_native_output_without_replacing_python(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    binary = tmp_path / "generate"
    binary.write_text(
        "#!/bin/sh\nprintf 'local answer'\nprintf 'timing info' >&2\n", encoding="utf-8"
    )
    binary.chmod(0o755)
    model = ResolvedModel(tmp_path / "model.gturbo", "test", None)
    plan = LaunchPlan("run", binary, model, (str(binary),), {})
    client = ElasticUMA(tmp_path)
    monkeypatch.setattr(client, "plan_run", lambda *_args, **_kwargs: plan)
    monkeypatch.setattr(sdk, "running_model_processes", lambda: ())
    result = client.generate("test", "hello")
    assert result.ok is True
    assert result.text == "local answer"
    assert result.diagnostics == "timing info"


def test_managed_server_waits_for_loopback_and_stops_owned_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    port_probe = socket.socket()
    port_probe.bind(("127.0.0.1", 0))
    port = int(port_probe.getsockname()[1])
    port_probe.close()
    binary = tmp_path / "server.py"
    binary.write_text(
        """#!/usr/bin/env python3
import socket
import sys

port = int(sys.argv[sys.argv.index('--port') + 1])
with socket.socket() as server:
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('127.0.0.1', port))
    server.listen()
    while True:
        connection, _ = server.accept()
        connection.close()
""",
        encoding="utf-8",
    )
    binary.chmod(0o755)
    model = ResolvedModel(tmp_path / "model.gturbo", "test", None)
    command = (str(binary), "--port", str(port))
    plan = LaunchPlan("serve", binary, model, command, {})
    client = ElasticUMA(tmp_path)
    monkeypatch.setattr(client, "plan_serve", lambda *_args, **_kwargs: plan)
    monkeypatch.setattr(sdk, "running_model_processes", lambda: ())
    handle = client.start_server("test", ready_timeout=3)
    try:
        assert handle.running is True
        assert handle.endpoint == f"http://127.0.0.1:{port}"
    finally:
        handle.stop()
    assert handle.running is False


def test_build_app_reuses_ready_runtime_and_writes_to_requested_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = Path(__file__).resolve().parents[1]
    runtime = tmp_path / "runtime"
    output = tmp_path / "output"
    client = ElasticUMA(project)
    monkeypatch.setattr(
        client,
        "runtime_status",
        lambda: {
            "ready": True,
            "runtime_root": str(runtime),
        },
    )

    def fake_run(command, **kwargs):
        assert kwargs == {"check": True}
        assert command[1:] == [str(runtime), "release", str(output)]
        executable = output / "ElasticUMA.app/Contents/MacOS/ElasticUMA"
        executable.parent.mkdir(parents=True)
        executable.write_bytes(b"app")
        executable.chmod(0o755)

    monkeypatch.setattr(sdk.subprocess, "run", fake_run)
    result = client.build_app(output_root=output)
    assert result.path == output / "ElasticUMA.app"
    assert result.runtime_path == runtime
