"""Language analyzer adapter contract.

Adapters emit the same ``functions`` map shape as Python (qualified names,
``calls`` / ``callers`` / ``complexity`` / ``simple_name``) for the fields they
can honestly fill. Fidelity differs by language — see each adapter's ``note``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class LanguageAdapter(Protocol):
    """Protocol for per-language repository map builders."""

    language: str
    extensions: frozenset[str]
    fidelity: str  # e.g. "ast", "best-effort"
    note: str

    def build_map(self, root: Path) -> dict[str, Any]:
        """Return ``{"language": ..., "functions": {...}}`` for files under root."""
        ...
