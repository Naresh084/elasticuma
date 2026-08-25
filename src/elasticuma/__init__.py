"""ElasticUMA Apple-Silicon inference and model tooling."""

from __future__ import annotations

from .sdk import (
    DownloadConfirmationRequired,
    ElasticUMA,
    ElasticUMAError,
    GenerationError,
    GenerationResult,
    MacAppBuild,
    ModelInfo,
    ServerHandle,
    ServerStartError,
    SetupPlan,
    SetupRefusedError,
    SetupResult,
)
from .version import __version__

__all__ = [
    "DownloadConfirmationRequired",
    "ElasticUMA",
    "ElasticUMAError",
    "GenerationError",
    "GenerationResult",
    "MacAppBuild",
    "ModelInfo",
    "ServerHandle",
    "ServerStartError",
    "SetupPlan",
    "SetupRefusedError",
    "SetupResult",
    "__version__",
]
