"""Stable, process-safe Python API for ElasticUMA.

The SDK deliberately wraps the lower-level catalog, storage, and launch modules
instead of exposing their repository-oriented arguments to applications.
"""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import time
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from .catalog import ModelProfile, load_profiles, resolve_profile
from .model_store import cache_root
from .runtime_provenance import runtime_asset_root
from .runtime_store import install_packed_model, packed_model_path, packed_preflight
from .serving import (
    LaunchPlan,
    catalog_paths,
    install_runtime,
    launch,
    run_plan,
    running_model_processes,
    runtime_root,
    runtime_status,
    serve_plan,
)
from .util import utc_now

SupportLevel = Literal["verified", "community"]
SetupAction = Literal["reuse", "install", "preflight-after-runtime"]
ResidencyMode = Literal["fixed", "os-managed"]


def _source_checkout_root() -> Path | None:
    configured = os.environ.get("ELASTICUMA_PROJECT_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "pyproject.toml").is_file() and (
            candidate / "runtime/patches/elasticuma-purgeable.patch"
        ).is_file():
            return candidate
    return None


def default_project_root() -> Path:
    """Return the source checkout or a private state directory for wheel users."""

    return _source_checkout_root() or (cache_root() / "state")


def _verified_model_path(path: Path) -> bool:
    return (
        path.is_dir()
        and (path / "manifest.json").is_file()
        and (path / "verified-install.json").is_file()
        and (path / "model_weights.bin").is_file()
    )


@dataclass(frozen=True)
class ModelInfo:
    """A catalog model with its exact support and local-install state."""

    id: str
    display_name: str
    architecture: str
    repo_id: str
    revision: str
    support: SupportLevel
    installed: bool
    model_path: Path
    minimum_ram_gib: int
    total_experts: int
    active_experts: int
    default_cache_slots: int
    default_hot_slots: int
    input_modalities: tuple[str, ...]
    evidence: str

    @property
    def verified(self) -> bool:
        return self.support == "verified"

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["model_path"] = str(self.model_path)
        payload["verified"] = self.verified
        return payload


@dataclass(frozen=True)
class SetupPlan:
    """A no-write explanation of what ``setup`` would do next."""

    model: ModelInfo
    runtime_action: Literal["reuse", "install"]
    model_action: SetupAction
    allowed: bool | None
    reasons: tuple[str, ...] = ()
    source_published_bytes: int | None = None
    disk_free_bytes: int | None = None
    disk_reserve_bytes: int | None = None

    @property
    def needs_confirmation(self) -> bool:
        return self.model_action == "install" and self.allowed is True

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["model"] = self.model.as_dict()
        payload["needs_confirmation"] = self.needs_confirmation
        return payload


@dataclass(frozen=True)
class SetupResult:
    """The verified model and runtime state produced by ``setup``."""

    model: ModelInfo
    runtime: dict[str, object]
    model_path: Path
    registration_manifest: Path
    reused: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "model": self.model.as_dict(),
            "runtime": self.runtime,
            "model_path": str(self.model_path),
            "registration_manifest": str(self.registration_manifest),
            "reused": self.reused,
        }


@dataclass(frozen=True)
class GenerationResult:
    """Captured output from one local generation."""

    text: str
    diagnostics: str
    returncode: int
    duration_seconds: float
    plan: LaunchPlan

    @property
    def ok(self) -> bool:
        return self.returncode == 0


@dataclass(frozen=True)
class MacAppBuild:
    """A packaged native app that shares ElasticUMA's runtime and model cache."""

    path: Path
    configuration: Literal["debug", "release"]
    runtime_path: Path

    def as_dict(self) -> dict[str, str]:
        return {
            "path": str(self.path),
            "configuration": self.configuration,
            "runtime_path": str(self.runtime_path),
        }


class ElasticUMAError(RuntimeError):
    """Base error raised by the high-level SDK."""


class SetupRefusedError(ElasticUMAError):
    def __init__(self, plan: SetupPlan) -> None:
        self.plan = plan
        message = "; ".join(plan.reasons) or "setup failed its safety checks"
        super().__init__(message)


class DownloadConfirmationRequired(ElasticUMAError):
    def __init__(self, plan: SetupPlan) -> None:
        self.plan = plan
        super().__init__(
            "model installation requires explicit consent; call setup(..., allow_download=True)"
        )


class GenerationError(ElasticUMAError):
    def __init__(self, result: GenerationResult) -> None:
        self.result = result
        detail = result.diagnostics.strip() or f"native runtime exited {result.returncode}"
        super().__init__(detail)


class ServerStartError(ElasticUMAError):
    """Raised when a managed local server does not become ready."""


@dataclass
class ServerHandle:
    """A server process owned by the calling Python application."""

    process: subprocess.Popen[bytes]
    endpoint: str
    log_path: Path
    plan: LaunchPlan

    @property
    def pid(self) -> int:
        return self.process.pid

    @property
    def running(self) -> bool:
        return self.process.poll() is None

    def wait(self, timeout: float | None = None) -> int:
        return self.process.wait(timeout=timeout)

    def read_logs(self) -> str:
        if not self.log_path.is_file():
            return ""
        return self.log_path.read_text(encoding="utf-8", errors="replace")

    def stop(self, timeout: float = 10.0) -> int:
        if self.process.poll() is not None:
            return int(self.process.returncode or 0)
        self.process.send_signal(signal.SIGINT)
        try:
            return self.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.process.terminate()
        try:
            return self.process.wait(timeout=min(timeout, 5.0))
        except subprocess.TimeoutExpired:
            self.process.kill()
            return self.process.wait(timeout=5.0)

    def __enter__(self) -> ServerHandle:
        return self

    def __exit__(self, *_args: object) -> None:
        self.stop()


class ElasticUMA:
    """High-level API shared by Python programs and the public CLI.

    ``project_root`` is normally discovered automatically. Source checkouts use
    their bundled runtime patch and community catalogs; installed wheels use a
    private state directory while keeping model files in the same canonical
    ElasticUMA cache.
    """

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        catalogs: Iterable[str | Path] = (),
    ) -> None:
        self.project_root = Path(project_root or default_project_root()).expanduser().resolve()
        self.catalogs = tuple(Path(path).expanduser().resolve() for path in catalogs)

    def _catalog_paths(self) -> tuple[Path, ...]:
        return catalog_paths(self.project_root, self.catalogs)

    def _profile(self, reference: str) -> ModelProfile:
        return resolve_profile(reference, extra_catalogs=self._catalog_paths())

    @staticmethod
    def _model_info(profile: ModelProfile) -> ModelInfo:
        path = packed_model_path(profile)
        return ModelInfo(
            id=profile.id,
            display_name=profile.display_name,
            architecture=profile.architecture,
            repo_id=profile.repo_id,
            revision=profile.revision,
            support="verified" if profile.verification == "admitted" else "community",
            installed=_verified_model_path(path),
            model_path=path,
            minimum_ram_gib=profile.minimum_ram_gib,
            total_experts=profile.total_experts,
            active_experts=profile.active_experts,
            default_cache_slots=profile.default_cache_slots,
            default_hot_slots=profile.default_hot_slots,
            input_modalities=profile.input_modalities,
            evidence=profile.evidence,
        )

    def models(self) -> tuple[ModelInfo, ...]:
        """List exact catalog entries and whether each is installed locally."""

        return tuple(self._model_info(profile) for profile in load_profiles(self._catalog_paths()))

    def model(self, reference: str) -> ModelInfo:
        """Resolve one id, alias, or pinned Hugging Face repository id."""

        return self._model_info(self._profile(reference))

    def runtime_status(self) -> dict[str, object]:
        return runtime_status(self.project_root)

    def plan_setup(self, reference: str) -> SetupPlan:
        """Inspect setup without building a runtime or downloading model bytes."""

        info = self.model(reference)
        status = self.runtime_status()
        if status["ready"] is not True:
            return SetupPlan(
                model=info,
                runtime_action="install",
                model_action="preflight-after-runtime",
                allowed=None,
                reasons=("model storage checks run after the native runtime is ready",),
            )
        payload = packed_preflight(runtime_root(self.project_root), self._profile(reference))
        return SetupPlan(
            model=info,
            runtime_action="reuse",
            model_action="reuse" if payload["verified_existing"] else "install",
            allowed=bool(payload["allowed"]),
            reasons=tuple(str(reason) for reason in payload["reasons"]),
            source_published_bytes=int(payload["source_published_bytes"]),
            disk_free_bytes=int(payload["disk_free_bytes"]),
            disk_reserve_bytes=int(payload["disk_reserve_bytes"]),
        )

    def setup(self, reference: str, *, allow_download: bool = False) -> SetupResult:
        """Build the pinned runtime and install one verified model exactly once.

        The SDK never prompts. A new model transfer requires
        ``allow_download=True``; an already verified installation is reused
        without that flag.
        """

        status = self.runtime_status()
        if status["ready"] is not True:
            status = install_runtime(self.project_root)
        plan = self.plan_setup(reference)
        if plan.allowed is not True:
            raise SetupRefusedError(plan)
        if plan.needs_confirmation and not allow_download:
            raise DownloadConfirmationRequired(plan)
        installed = install_packed_model(
            self.project_root,
            runtime_root(self.project_root),
            self._profile(reference),
        )
        return SetupResult(
            model=self.model(reference),
            runtime=status,
            model_path=Path(installed["model_path"]),
            registration_manifest=Path(installed["registration_manifest"]),
            reused=plan.model_action == "reuse",
        )

    def plan_run(
        self,
        reference: str,
        prompt: str,
        *,
        max_new: int = 256,
        max_context: int = 4096,
        cache_slots: int | None = None,
        hot_slots: int | None = None,
        residency: ResidencyMode = "os-managed",
        seed: int | None = None,
        diagnostics: bool = False,
    ) -> LaunchPlan:
        return run_plan(
            self.project_root,
            reference,
            prompt,
            max_new=max_new,
            max_context=max_context,
            cache_slots=cache_slots,
            hot_slots=hot_slots,
            residency=residency,
            seed=seed,
            diagnostics=diagnostics,
            extra_catalogs=self.catalogs,
        )

    def plan_serve(
        self,
        reference: str,
        *,
        port: int = 8080,
        max_context: int = 16384,
        queue_limit: int = 4,
        cache_slots: int | None = None,
        hot_slots: int | None = None,
        residency: ResidencyMode = "os-managed",
        model_id: str | None = None,
    ) -> LaunchPlan:
        return serve_plan(
            self.project_root,
            reference,
            port=port,
            max_context=max_context,
            queue_limit=queue_limit,
            cache_slots=cache_slots,
            hot_slots=hot_slots,
            residency=residency,
            model_id=model_id,
            extra_catalogs=self.catalogs,
        )

    def generate(
        self,
        reference: str,
        prompt: str,
        *,
        max_new: int = 256,
        max_context: int = 4096,
        cache_slots: int | None = None,
        hot_slots: int | None = None,
        residency: ResidencyMode = "os-managed",
        seed: int | None = None,
        diagnostics: bool = False,
        timeout: float | None = None,
        check: bool = True,
    ) -> GenerationResult:
        """Generate once and capture text without replacing the Python process."""

        plan = self.plan_run(
            reference,
            prompt,
            max_new=max_new,
            max_context=max_context,
            cache_slots=cache_slots,
            hot_slots=hot_slots,
            residency=residency,
            seed=seed,
            diagnostics=diagnostics,
        )
        conflicts = running_model_processes()
        if conflicts:
            detail = "\n".join(f"  {row}" for row in conflicts)
            raise ElasticUMAError(f"another model process is already running:\n{detail}")
        environment = os.environ.copy()
        environment.update(plan.environment)
        started = time.monotonic()
        completed = subprocess.run(
            list(plan.command),
            capture_output=True,
            check=False,
            env=environment,
            timeout=timeout,
        )
        result = GenerationResult(
            text=completed.stdout.decode("utf-8", errors="replace"),
            diagnostics=completed.stderr.decode("utf-8", errors="replace"),
            returncode=completed.returncode,
            duration_seconds=time.monotonic() - started,
            plan=plan,
        )
        if check and not result.ok:
            raise GenerationError(result)
        return result

    def start_server(
        self,
        reference: str,
        *,
        port: int = 8080,
        max_context: int = 16384,
        queue_limit: int = 4,
        cache_slots: int | None = None,
        hot_slots: int | None = None,
        residency: ResidencyMode = "os-managed",
        model_id: str | None = None,
        ready_timeout: float = 60.0,
    ) -> ServerHandle:
        """Start an owned background server and wait for its loopback port."""

        if ready_timeout <= 0:
            raise ValueError("ready_timeout must be positive")
        plan = self.plan_serve(
            reference,
            port=port,
            max_context=max_context,
            queue_limit=queue_limit,
            cache_slots=cache_slots,
            hot_slots=hot_slots,
            residency=residency,
            model_id=model_id,
        )
        conflicts = running_model_processes()
        if conflicts:
            detail = "\n".join(f"  {row}" for row in conflicts)
            raise ServerStartError(f"another model process is already running:\n{detail}")
        port_index = plan.command.index("--port") + 1
        port = int(plan.command[port_index])
        log_root = cache_root() / "logs"
        log_root.mkdir(parents=True, exist_ok=True)
        stamp = utc_now().replace(":", "-")
        log_path = log_root / f"server-{stamp}.log"
        environment = os.environ.copy()
        environment.update(plan.environment)
        with log_path.open("ab", buffering=0) as log:
            process = subprocess.Popen(
                list(plan.command),
                env=environment,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        handle = ServerHandle(
            process=process,
            endpoint=f"http://127.0.0.1:{port}",
            log_path=log_path,
            plan=plan,
        )
        deadline = time.monotonic() + ready_timeout
        while time.monotonic() < deadline:
            if process.poll() is not None:
                logs = handle.read_logs().strip()
                raise ServerStartError(logs or f"server exited with code {process.returncode}")
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                    return handle
            except OSError:
                time.sleep(0.1)
        handle.stop()
        raise ServerStartError(
            f"server did not listen on 127.0.0.1:{port} within {ready_timeout:.1f}s; see {log_path}"
        )

    def build_app(
        self,
        *,
        output_root: str | Path | None = None,
        configuration: Literal["debug", "release"] = "release",
    ) -> MacAppBuild:
        """Build and ad-hoc sign the native Mac app without model downloads."""

        if configuration not in {"debug", "release"}:
            raise ValueError("configuration must be debug or release")
        status = self.runtime_status()
        if status["ready"] is not True:
            status = install_runtime(self.project_root)
        runtime_path = Path(str(status["runtime_root"]))
        script = runtime_asset_root(self.project_root) / "scripts/package_macos_app.sh"
        if not script.is_file():
            raise ElasticUMAError(f"Mac app packager is missing: {script}")
        destination = Path(output_root or (cache_root() / "app")).expanduser().resolve()
        subprocess.run(
            [str(script), str(runtime_path), configuration, str(destination)],
            check=True,
        )
        app_path = destination / "ElasticUMA.app"
        executable = app_path / "Contents/MacOS/ElasticUMA"
        if not executable.is_file() or not os.access(executable, os.X_OK):
            raise ElasticUMAError(f"Mac app build did not produce {executable}")
        return MacAppBuild(app_path, configuration, runtime_path)

    def open_app(
        self,
        *,
        build_if_missing: bool = True,
        output_root: str | Path | None = None,
    ) -> Path:
        """Open the packaged native app, building it first when requested."""

        destination = Path(output_root or (cache_root() / "app")).expanduser().resolve()
        app_path = destination / "ElasticUMA.app"
        if not app_path.is_dir():
            if not build_if_missing:
                raise ElasticUMAError(f"Mac app is not built at {app_path}")
            app_path = self.build_app(output_root=destination).path
        subprocess.run(["/usr/bin/open", str(app_path)], check=True)
        return app_path

    @staticmethod
    def launch(plan: LaunchPlan) -> None:
        """Replace the current process with a validated plan (used by the CLI)."""

        launch(plan)
