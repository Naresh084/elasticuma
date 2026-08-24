from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from elasticuma.schema import RuntimeResult


class RuntimeAdapter(ABC):
    @abstractmethod
    def parse(self, *, stdout_path: Path, stderr_path: Path, result_path: Path) -> RuntimeResult:
        """Parse one completed runtime invocation or raise on ambiguity."""
