from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any

_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_KEYS = {
    "id",
    "aliases",
    "display_name",
    "architecture",
    "repo_id",
    "revision",
    "source_index_sha256",
    "packed_model_id",
    "repack_selector",
    "path_prefix",
    "layers",
    "total_experts",
    "active_experts",
    "default_cache_slots",
    "default_hot_slots",
    "minimum_ram_gib",
    "input_modalities",
    "verification",
    "evidence",
}


@dataclass(frozen=True)
class ModelProfile:
    id: str
    aliases: tuple[str, ...]
    display_name: str
    architecture: str
    repo_id: str
    revision: str
    source_index_sha256: str
    packed_model_id: str
    repack_selector: str
    path_prefix: str
    layers: int
    total_experts: int
    active_experts: int
    default_cache_slots: int
    default_hot_slots: int
    minimum_ram_gib: int
    input_modalities: tuple[str, ...]
    verification: str
    evidence: str
    source: str

    @property
    def selector(self) -> str:
        """Backward-compatible profile name used by the research harness."""
        return self.id

    def public_dict(self) -> dict[str, object]:
        return asdict(self)


def _string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"model profile field {key!r} must be a non-empty string")
    return value.strip()


def _positive_int(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"model profile field {key!r} must be a positive integer")
    return value


def _input_modalities(payload: dict[str, Any]) -> tuple[str, ...]:
    value = payload.get("input_modalities", ["text"])
    allowed = {"text", "image", "audio", "video"}
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, str) and item in allowed for item in value)
        or len(set(value)) != len(value)
    ):
        raise ValueError(
            "model profile input_modalities must be a unique non-empty list of "
            "text, image, audio, or video"
        )
    return tuple(value)


def parse_profile(payload: dict[str, Any], *, source: str) -> ModelProfile:
    unknown = set(payload) - _ALLOWED_KEYS
    if unknown:
        raise ValueError(f"unknown model profile fields in {source}: {sorted(unknown)}")
    identifier = _string(payload, "id")
    if not _IDENTIFIER.fullmatch(identifier):
        raise ValueError(f"invalid model profile id {identifier!r}")
    aliases_value = payload.get("aliases", [])
    if not isinstance(aliases_value, list) or not all(
        isinstance(item, str) and _IDENTIFIER.fullmatch(item) for item in aliases_value
    ):
        raise ValueError("model profile aliases must be safe lowercase identifiers")
    aliases = tuple(dict.fromkeys(item.strip() for item in aliases_value))
    if identifier in aliases:
        raise ValueError("model profile aliases must not repeat the profile id")
    repo_id = _string(payload, "repo_id")
    if repo_id.count("/") != 1:
        raise ValueError("model profile repo_id must use owner/name form")
    revision = _string(payload, "revision")
    if not _COMMIT.fullmatch(revision):
        raise ValueError("model profile revision must be an immutable 40-character commit")
    source_hash = _string(payload, "source_index_sha256")
    if not _SHA256.fullmatch(source_hash):
        raise ValueError("model profile source_index_sha256 must be lowercase SHA-256")
    path_prefix = _string(payload, "path_prefix")
    if not _IDENTIFIER.fullmatch(path_prefix):
        raise ValueError("model profile path_prefix must be a safe lowercase identifier")

    layers = _positive_int(payload, "layers")
    total_experts = _positive_int(payload, "total_experts")
    active_experts = _positive_int(payload, "active_experts")
    cache_slots = _positive_int(payload, "default_cache_slots")
    hot_slots = _positive_int(payload, "default_hot_slots")
    if active_experts > total_experts:
        raise ValueError("active_experts cannot exceed total_experts")
    if cache_slots > total_experts:
        raise ValueError("default_cache_slots cannot exceed total_experts")
    if hot_slots > cache_slots:
        raise ValueError("default_hot_slots cannot exceed default_cache_slots")
    verification = _string(payload, "verification")
    if verification not in {"admitted", "community"}:
        raise ValueError("verification must be admitted or community")
    return ModelProfile(
        id=identifier,
        aliases=aliases,
        display_name=_string(payload, "display_name"),
        architecture=_string(payload, "architecture"),
        repo_id=repo_id,
        revision=revision,
        source_index_sha256=source_hash,
        packed_model_id=_string(payload, "packed_model_id"),
        repack_selector=_string(payload, "repack_selector"),
        path_prefix=path_prefix,
        layers=layers,
        total_experts=total_experts,
        active_experts=active_experts,
        default_cache_slots=cache_slots,
        default_hot_slots=hot_slots,
        minimum_ram_gib=_positive_int(payload, "minimum_ram_gib"),
        input_modalities=_input_modalities(payload),
        verification=verification,
        evidence=_string(payload, "evidence"),
        source=source,
    )


def _profiles_from_document(payload: Any, *, source: str) -> list[ModelProfile]:
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError(f"model catalog {source} must use schema_version 1")
    rows = payload.get("models")
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"model catalog {source} must contain a non-empty models list")
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError(f"model catalog {source} contains a non-object model entry")
    return [parse_profile(row, source=source) for row in rows]


def _read_catalog(path: Path) -> list[ModelProfile]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return _profiles_from_document(payload, source=str(path))


def builtin_profiles() -> tuple[ModelProfile, ...]:
    resource = files("elasticuma").joinpath("model_catalog.json")
    payload = json.loads(resource.read_text(encoding="utf-8"))
    return tuple(_profiles_from_document(payload, source="builtin:model_catalog.json"))


def load_profiles(extra_catalogs: Iterable[Path] = ()) -> tuple[ModelProfile, ...]:
    profiles = [*builtin_profiles()]
    for path in extra_catalogs:
        profiles.extend(_read_catalog(path))
    names: dict[str, str] = {}
    for profile in profiles:
        for name in (profile.id, *profile.aliases):
            if previous := names.get(name):
                raise ValueError(
                    f"model name {name!r} from {profile.source} conflicts with {previous}"
                )
            names[name] = profile.source
    return tuple(profiles)


def project_catalog_paths(project_root: Path) -> tuple[Path, ...]:
    root = project_root / "models"
    return tuple(sorted(root.glob("*.json"))) if root.is_dir() else ()


def resolve_profile(
    name: str,
    *,
    extra_catalogs: Iterable[Path] = (),
) -> ModelProfile:
    matches = [
        profile
        for profile in load_profiles(extra_catalogs)
        if name in {profile.id, profile.repo_id, profile.packed_model_id} or name in profile.aliases
    ]
    if len(matches) != 1:
        available = ", ".join(profile.id for profile in load_profiles(extra_catalogs))
        raise ValueError(f"unknown model profile {name!r}; available: {available}")
    return matches[0]
