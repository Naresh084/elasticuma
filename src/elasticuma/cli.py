from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .admission import admit_experiment
from .analysis import analyze_admitted, purgeable_comparison
from .catalog import load_profiles, resolve_profile
from .config import load_experiment
from .macos import memory_snapshot, power_snapshot, safe_public_hardware_dict
from .model_store import cache_root, fetch, list_registered, preflight
from .native_pressure import monitor_binary
from .pressure import run_pressure_worker, validate_pressure_request
from .runner import run_experiment
from .runtime_store import (
    install_packed_gemma4,
    install_packed_model,
    install_packed_qwen36,
    packed_gemma4_preflight,
    packed_model_path,
    packed_preflight,
)
from .serving import (
    catalog_paths,
    install_runtime,
    launch,
    run_plan,
    runtime_root,
    runtime_status,
    serve_plan,
)
from .util import atomic_write_json, gib, jsonable, sha256_file, utc_now
from .version import __version__

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _emit(value: Any, *, as_json: bool = True) -> None:
    if as_json:
        print(json.dumps(jsonable(value), indent=2, sort_keys=True))
    else:
        print(value)


def _doctor(_args: argparse.Namespace) -> int:
    tools = {
        name: shutil.which(name)
        for name in ("git", "swift", "xcodebuild", "python3", "uv", "jq", "rg")
    }
    runtime = runtime_status(PROJECT_ROOT)
    build_ready = all(tools[name] for name in ("git", "swift", "xcodebuild"))
    payload = {
        "schema_version": 1,
        "version": __version__,
        "hardware": safe_public_hardware_dict(),
        "memory": memory_snapshot(),
        "power": power_snapshot(),
        "cache_root": str(cache_root()),
        "registered_models": list_registered(PROJECT_ROOT),
        "tools": tools,
        "native_pressure_monitor": str(monitor_binary(PROJECT_ROOT)),
        "native_pressure_monitor_ready": monitor_binary(PROJECT_ROOT).is_file(),
        "runtime": runtime,
        "ready_for_runtime_build": build_ready,
        "serve_ready": runtime["ready"],
        "research_ready": all(tools.values()) and monitor_binary(PROJECT_ROOT).is_file(),
        "ready": runtime["ready"],
    }
    _emit(payload)
    return 0 if payload["ready"] else 1


def _model_preflight(args: argparse.Namespace) -> int:
    plan = preflight(args.repo, args.revision)
    payload = asdict(plan)
    payload["published_gib"] = gib(plan.published_bytes)
    payload["disk_free_gib"] = gib(plan.disk_free_bytes)
    payload["disk_reserve_gib"] = gib(plan.disk_reserve_bytes)
    _emit(payload)
    return 0 if plan.action != "refuse" else 2


def _model_fetch(args: argparse.Namespace) -> int:
    plan, snapshot = fetch(PROJECT_ROOT, args.repo, args.revision)
    _emit({"plan": plan, "snapshot": snapshot})
    return 0


def _model_list(_args: argparse.Namespace) -> int:
    _emit(list_registered(PROJECT_ROOT))
    return 0


def _extra_catalogs(args: argparse.Namespace) -> tuple[Path, ...]:
    return tuple(Path(value) for value in getattr(args, "catalog", []) or [])


def _model_catalog(args: argparse.Namespace) -> int:
    paths = catalog_paths(PROJECT_ROOT, _extra_catalogs(args))
    rows = []
    for profile in load_profiles(paths):
        payload = profile.public_dict()
        model_path = packed_model_path(profile)
        payload["model_path"] = str(model_path)
        payload["installed"] = (
            model_path.is_dir()
            and (model_path / "manifest.json").is_file()
            and (model_path / "verified-install.json").is_file()
            and (model_path / "model_weights.bin").is_file()
        )
        rows.append(payload)
    _emit(rows)
    return 0


def _model_profile_preflight(args: argparse.Namespace) -> int:
    profile = resolve_profile(
        args.profile,
        extra_catalogs=catalog_paths(PROJECT_ROOT, _extra_catalogs(args)),
    )
    plan = packed_preflight(Path(args.runtime_root), profile)
    _emit(plan)
    return 0 if plan["allowed"] else 2


def _model_profile_install(args: argparse.Namespace) -> int:
    profile = resolve_profile(
        args.profile,
        extra_catalogs=catalog_paths(PROJECT_ROOT, _extra_catalogs(args)),
    )
    _emit(install_packed_model(PROJECT_ROOT, Path(args.runtime_root), profile))
    return 0


def _runtime_status(_args: argparse.Namespace) -> int:
    status = runtime_status(PROJECT_ROOT)
    _emit(status)
    return 0 if status["ready"] else 1


def _runtime_install(_args: argparse.Namespace) -> int:
    _emit(install_runtime(PROJECT_ROOT))
    return 0


def _serve(args: argparse.Namespace) -> int:
    plan = serve_plan(
        PROJECT_ROOT,
        args.model,
        port=args.port,
        max_context=args.max_context,
        queue_limit=args.queue_limit,
        cache_slots=args.cache_slots,
        hot_slots=args.hot_slots,
        residency=args.residency,
        model_id=args.model_id,
        extra_catalogs=_extra_catalogs(args),
    )
    if args.dry_run:
        _emit(plan.public_dict())
        return 0
    launch(plan)
    return 0


def _run(args: argparse.Namespace) -> int:
    plan = run_plan(
        PROJECT_ROOT,
        args.model,
        args.prompt,
        max_new=args.max_new,
        max_context=args.max_context,
        cache_slots=args.cache_slots,
        hot_slots=args.hot_slots,
        residency=args.residency,
        seed=args.seed,
        extra_catalogs=_extra_catalogs(args),
    )
    if args.dry_run:
        _emit(plan.public_dict())
        return 0
    launch(plan)
    return 0


def _packed_preflight(args: argparse.Namespace) -> int:
    plan = packed_preflight(Path(args.runtime_root))
    _emit(plan)
    return 0 if plan["allowed"] else 2


def _packed_install(args: argparse.Namespace) -> int:
    _emit(install_packed_qwen36(PROJECT_ROOT, Path(args.runtime_root)))
    return 0


def _packed_gemma4_preflight(args: argparse.Namespace) -> int:
    plan = packed_gemma4_preflight(Path(args.runtime_root))
    _emit(plan)
    return 0 if plan["allowed"] else 2


def _packed_gemma4_install(args: argparse.Namespace) -> int:
    _emit(install_packed_gemma4(PROJECT_ROOT, Path(args.runtime_root)))
    return 0


def _pressure_check(args: argparse.Namespace) -> int:
    plan = validate_pressure_request(args.mib)
    _emit(plan)
    return 0 if plan.allowed else 2


def _pressure_worker(args: argparse.Namespace) -> int:
    return run_pressure_worker(
        args.mib,
        ready_path=Path(args.ready),
        receipt_path=Path(args.receipt),
    )


def _experiment_validate(args: argparse.Namespace) -> int:
    spec = load_experiment(Path(args.config), PROJECT_ROOT)
    _emit(spec)
    return 0


def _experiment_run(args: argparse.Namespace) -> int:
    spec = load_experiment(Path(args.config), PROJECT_ROOT)
    records = run_experiment(PROJECT_ROOT, spec)
    admitted_path = admit_experiment(PROJECT_ROOT, records, spec)
    _emit(
        {
            "experiment": spec.name,
            "raw_records": len(records),
            "admitted_artifact": admitted_path,
        }
    )
    return 0


def _experiment_analyze(args: argparse.Namespace) -> int:
    source = Path(args.input)
    if source.is_dir():
        candidates = sorted(source.glob("*.json"))
        if len(candidates) != 1:
            raise ValueError(
                "directory must contain exactly one admitted JSON artifact, "
                f"found {len(candidates)}"
            )
        source = candidates[0]
    paths = analyze_admitted(source, PROJECT_ROOT / "artifacts/figures")
    _emit({"analysis": paths[0], "summary_csv": paths[1], "gate1_report": paths[2]})
    return 0


def _experiment_analyze_purgeable(args: argparse.Namespace) -> int:
    source = Path(args.input)
    with source.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict) or payload.get("complete") is not True:
        raise ValueError("purgeable analysis requires a complete admitted experiment")
    records = payload.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError("admitted experiment has no records")
    analysis = purgeable_comparison(
        records,
        candidate_arm=args.candidate,
        baseline_arms=args.baseline,
    )
    output = (
        Path(args.output)
        if args.output
        else (PROJECT_ROOT / "artifacts/figures" / f"{source.stem}-purgeable-analysis.json")
    )
    atomic_write_json(
        output,
        {
            "schema_version": 1,
            "created_at": utc_now(),
            "source": str(source),
            "source_sha256": sha256_file(source),
            **analysis,
        },
    )
    _emit({"analysis": output})
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="elasticuma")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
        metavar="{doctor,runtime,model,serve,run,pressure,experiment}",
    )

    doctor = subparsers.add_parser("doctor", help="emit privacy-safe hardware and tool readiness")
    doctor.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    doctor.set_defaults(func=_doctor)

    runtime = subparsers.add_parser("runtime", help="build or inspect the native runtime")
    runtime_sub = runtime.add_subparsers(dest="runtime_command", required=True)
    runtime_install = runtime_sub.add_parser("install", help="clone, patch, and build the runtime")
    runtime_install.set_defaults(func=_runtime_install)
    runtime_check = runtime_sub.add_parser("status", help="report runtime build readiness")
    runtime_check.set_defaults(func=_runtime_status)

    model = subparsers.add_parser("model", help="manage the canonical model store")
    model_sub = model.add_subparsers(
        dest="model_command",
        required=True,
        metavar="{catalog,preflight,install,list}",
    )
    catalog = model_sub.add_parser("catalog", help="list built-in and custom model profiles")
    catalog.add_argument("--catalog", action="append", default=[])
    catalog.set_defaults(func=_model_catalog)
    profile_check = model_sub.add_parser("preflight", help="safety-check a model installation")
    profile_check.add_argument("--profile", required=True)
    profile_check.add_argument("--catalog", action="append", default=[])
    profile_check.add_argument(
        "--runtime-root",
        default=str(runtime_root(PROJECT_ROOT)),
    )
    profile_check.set_defaults(func=_model_profile_preflight)
    profile_install = model_sub.add_parser("install", help="install one catalog model once")
    profile_install.add_argument("--profile", required=True)
    profile_install.add_argument("--catalog", action="append", default=[])
    profile_install.add_argument(
        "--runtime-root",
        default=str(runtime_root(PROJECT_ROOT)),
    )
    profile_install.set_defaults(func=_model_profile_install)
    for name, function in (("hf-preflight", _model_preflight), ("hf-fetch", _model_fetch)):
        command = model_sub.add_parser(name)
        command.add_argument("--repo", required=True)
        command.add_argument("--revision", required=True)
        command.set_defaults(func=function)
    model_list = model_sub.add_parser("list", help="show registered local model receipts")
    model_list.set_defaults(func=_model_list)
    packed_check = model_sub.add_parser("packed-preflight")
    packed_check.add_argument(
        "--runtime-root",
        default=str(runtime_root(PROJECT_ROOT)),
    )
    packed_check.set_defaults(func=_packed_preflight)
    packed_install = model_sub.add_parser("install-qwen36")
    packed_install.add_argument(
        "--runtime-root",
        default=str(runtime_root(PROJECT_ROOT)),
    )
    packed_install.set_defaults(func=_packed_install)
    gemma_check = model_sub.add_parser("gemma4-packed-preflight")
    gemma_check.add_argument(
        "--runtime-root",
        default=str(runtime_root(PROJECT_ROOT)),
    )
    gemma_check.set_defaults(func=_packed_gemma4_preflight)
    gemma_install = model_sub.add_parser("install-gemma4")
    gemma_install.add_argument(
        "--runtime-root",
        default=str(runtime_root(PROJECT_ROOT)),
    )
    gemma_install.set_defaults(func=_packed_gemma4_install)

    serve = subparsers.add_parser("serve", help="start the loopback OpenAI/Anthropic API")
    serve.add_argument("--model", required=True, help="catalog profile or verified .gturbo path")
    serve.add_argument("--catalog", action="append", default=[], help="additional catalog JSON")
    serve.add_argument("--port", type=int, default=8080, help="loopback port (default 8080)")
    serve.add_argument("--model-id", help="API model id (default profile/manifest id)")
    serve.add_argument(
        "--max-context", type=int, default=16384, help="context tokens (default 16384)"
    )
    serve.add_argument(
        "--queue-limit", type=int, default=4, help="maximum queued requests (default 4)"
    )
    serve.add_argument("--cache-slots", type=int, help="logical expert slots per layer")
    serve.add_argument("--hot-slots", type=int, help="nonvolatile expert slots per layer")
    serve.add_argument(
        "--residency",
        choices=("fixed", "os-managed"),
        default="os-managed",
        help="expert residency policy (default os-managed)",
    )
    serve.add_argument("--dry-run", action="store_true", help="print the exact launch plan")
    serve.set_defaults(func=_serve)

    run_once = subparsers.add_parser("run", help="generate once from a catalog model or path")
    run_once.add_argument("--model", required=True, help="catalog profile or verified .gturbo path")
    run_once.add_argument("--prompt", required=True, help="raw generation prompt")
    run_once.add_argument("--catalog", action="append", default=[], help="additional catalog JSON")
    run_once.add_argument("--max-new", type=int, default=256, help="token limit (default 256)")
    run_once.add_argument(
        "--max-context", type=int, default=4096, help="context tokens (default 4096)"
    )
    run_once.add_argument("--cache-slots", type=int, help="logical expert slots per layer")
    run_once.add_argument("--hot-slots", type=int, help="nonvolatile expert slots per layer")
    run_once.add_argument(
        "--residency",
        choices=("fixed", "os-managed"),
        default="os-managed",
        help="expert residency policy (default os-managed)",
    )
    run_once.add_argument("--seed", type=int, help="deterministic sampling seed")
    run_once.add_argument("--dry-run", action="store_true", help="print the exact launch plan")
    run_once.set_defaults(func=_run)

    pressure = subparsers.add_parser("pressure", help="validate a bounded live-pressure request")
    pressure.add_argument("--mib", type=int, required=True)
    pressure.set_defaults(func=_pressure_check)

    worker = subparsers.add_parser("_pressure-worker")
    worker.add_argument("--mib", type=int, required=True)
    worker.add_argument("--ready", required=True)
    worker.add_argument("--receipt", required=True)
    worker.set_defaults(func=_pressure_worker)

    experiment = subparsers.add_parser(
        "experiment", help="run or analyze immutable research protocols"
    )
    experiment_sub = experiment.add_subparsers(dest="experiment_command", required=True)
    validate = experiment_sub.add_parser("validate-config")
    validate.add_argument("--config", required=True)
    validate.set_defaults(func=_experiment_validate)
    run = experiment_sub.add_parser("run")
    run.add_argument("--config", required=True)
    run.set_defaults(func=_experiment_run)
    analyze = experiment_sub.add_parser("analyze")
    analyze.add_argument("--input", required=True)
    analyze.set_defaults(func=_experiment_analyze)
    purgeable = experiment_sub.add_parser("analyze-purgeable")
    purgeable.add_argument("--input", required=True)
    purgeable.add_argument("--candidate", required=True)
    purgeable.add_argument("--baseline", action="append", required=True)
    purgeable.add_argument("--output")
    purgeable.set_defaults(func=_experiment_analyze_purgeable)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"elasticuma: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
